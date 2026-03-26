from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import dateparse, timezone

from core.models import Customer, IngredientMovement, Order, Pizza, RecipeItem, Sale, SaleItem


def _to_money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _movement_datetime(business_date):
    movement_dt = timezone.now()
    parsed_business_date = dateparse.parse_date(str(business_date))
    if parsed_business_date:
        movement_dt = timezone.make_aware(
            timezone.datetime.combine(parsed_business_date, timezone.datetime.min.time())
        )
    return movement_dt


def _get_recipe_items(pizza):
    recipe_items = RecipeItem.objects.select_related("ingredient").filter(pizza=pizza)
    if not recipe_items.exists():
        raise ValidationError("La pizza no tiene receta.")
    return recipe_items


def _consume_stock(pizza, quantity, movement_dt, reference):
    total_unit_cost = Decimal("0")
    recipe_items = _get_recipe_items(pizza)
    for recipe_item in recipe_items:
        ingredient = recipe_item.ingredient
        if not ingredient.is_active:
            raise ValidationError("La receta contiene un insumo inactivo.")

        consumed = recipe_item.quantity * Decimal(quantity)
        ingredient.current_stock = ingredient.current_stock - consumed
        ingredient.save(update_fields=["current_stock", "updated_at"])

        movement = IngredientMovement(
            ingredient=ingredient,
            movement_type=IngredientMovement.MovementType.SALE_CONSUMPTION,
            direction=IngredientMovement.Direction.OUT,
            quantity=consumed,
            created_at=movement_dt,
            reference=reference,
        )
        movement.full_clean()
        movement.save()

        total_unit_cost += recipe_item.quantity * ingredient.unit_price
    return _to_money(total_unit_cost)


def _restore_stock_for_item(sale_item, movement_dt, reference):
    recipe_items = RecipeItem.objects.select_related("ingredient").filter(pizza=sale_item.pizza)
    for recipe_item in recipe_items:
        ingredient = recipe_item.ingredient
        restored = recipe_item.quantity * Decimal(sale_item.quantity)
        ingredient.current_stock = ingredient.current_stock + restored
        ingredient.save(update_fields=["current_stock", "updated_at"])

        movement = IngredientMovement(
            ingredient=ingredient,
            movement_type=IngredientMovement.MovementType.MANUAL_ADJUSTMENT,
            direction=IngredientMovement.Direction.IN,
            quantity=restored,
            created_at=movement_dt,
            reference=reference,
        )
        movement.full_clean()
        movement.save()


def _resolve_customer(customer_id=None, customer_data=None):
    if customer_data:
        first_name = (customer_data.get("first_name") or "").strip()
        last_name = (customer_data.get("last_name") or "").strip()
        phone = (customer_data.get("phone") or "").strip()
        if not first_name or not last_name or not phone:
            raise ValidationError("Los datos del cliente nuevo son obligatorios.")
        return Customer.objects.create(first_name=first_name, last_name=last_name, phone=phone)

    if customer_id:
        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
        if not customer:
            raise ValidationError("No se encontró el cliente.")
        return customer

    raise ValidationError("Se requiere un cliente para registrar la venta.")


def create_sale(business_date, notes, items, reference_prefix="SALE", customer_id=None, customer_data=None):
    if not items:
        raise ValidationError("Se requiere al menos un ítem de venta.")

    with transaction.atomic():
        customer = _resolve_customer(customer_id=customer_id, customer_data=customer_data)
        sale = Sale.objects.create(business_date=business_date, notes=notes, customer=customer)
        total_revenue = Decimal("0.00")
        total_cost = Decimal("0.00")
        total_profit = Decimal("0.00")
        movement_dt = _movement_datetime(business_date)
        for item in items:
            pizza = Pizza.objects.filter(id=item.get("pizza_id")).first()
            quantity = item.get("quantity") or 0

            if not pizza:
                raise ValidationError("No se encontró la pizza.")
            if not pizza.is_active:
                raise ValidationError("La pizza está inactiva y no puede venderse.")
            if quantity <= 0:
                raise ValidationError("La cantidad debe ser mayor que cero.")

            applied_unit_price = _to_money(pizza.sale_price)
            calculated_unit_cost = _consume_stock(
                pizza=pizza,
                quantity=quantity,
                movement_dt=movement_dt,
                reference=f"{reference_prefix}:{sale.id}",
            )
            calculated_unit_profit = _to_money(applied_unit_price - calculated_unit_cost)

            SaleItem.objects.create(
                sale=sale,
                pizza=pizza,
                quantity=quantity,
                applied_unit_price=applied_unit_price,
                calculated_unit_cost=calculated_unit_cost,
                calculated_unit_profit=calculated_unit_profit,
            )

            total_revenue += applied_unit_price * Decimal(quantity)
            total_cost += calculated_unit_cost * Decimal(quantity)
            total_profit += calculated_unit_profit * Decimal(quantity)

        sale.total_revenue = _to_money(total_revenue)
        sale.total_cost = _to_money(total_cost)
        sale.total_profit = _to_money(total_profit)
        sale.save(update_fields=["total_revenue", "total_cost", "total_profit"])

        return sale


def update_sale(sale, business_date, notes, items, customer_id=None, customer_data=None):
    if not items:
        raise ValidationError("Se requiere al menos un ítem de venta.")

    with transaction.atomic():
        customer = _resolve_customer(customer_id=customer_id, customer_data=customer_data)
        movement_dt = _movement_datetime(business_date)
        previous_items = list(sale.items.select_related("pizza").all())
        for previous_item in previous_items:
            _restore_stock_for_item(previous_item, movement_dt, f"UPDATE_REVERT:{sale.id}")
        sale.items.all().delete()

        total_revenue = Decimal("0.00")
        total_cost = Decimal("0.00")
        total_profit = Decimal("0.00")
        for item in items:
            pizza = Pizza.objects.filter(id=item.get("pizza_id")).first()
            quantity = item.get("quantity") or 0

            if not pizza:
                raise ValidationError("No se encontró la pizza.")
            if not pizza.is_active:
                raise ValidationError("La pizza está inactiva y no puede venderse.")
            if quantity <= 0:
                raise ValidationError("La cantidad debe ser mayor que cero.")

            applied_unit_price = _to_money(pizza.sale_price)
            calculated_unit_cost = _consume_stock(
                pizza=pizza,
                quantity=quantity,
                movement_dt=movement_dt,
                reference=f"SALE:{sale.id}",
            )
            calculated_unit_profit = _to_money(applied_unit_price - calculated_unit_cost)

            SaleItem.objects.create(
                sale=sale,
                pizza=pizza,
                quantity=quantity,
                applied_unit_price=applied_unit_price,
                calculated_unit_cost=calculated_unit_cost,
                calculated_unit_profit=calculated_unit_profit,
            )

            total_revenue += applied_unit_price * Decimal(quantity)
            total_cost += calculated_unit_cost * Decimal(quantity)
            total_profit += calculated_unit_profit * Decimal(quantity)

        sale.business_date = business_date
        sale.customer = customer
        sale.notes = notes
        sale.total_revenue = _to_money(total_revenue)
        sale.total_cost = _to_money(total_cost)
        sale.total_profit = _to_money(total_profit)
        sale.save(update_fields=["business_date", "customer", "notes", "total_revenue", "total_cost", "total_profit"])
        return sale


def delete_sale(sale):
    with transaction.atomic():
        movement_dt = _movement_datetime(sale.business_date)
        for sale_item in sale.items.select_related("pizza").all():
            _restore_stock_for_item(sale_item, movement_dt, f"DELETE_REVERT:{sale.id}")
        sale.delete()


def close_sales_for_business_date(business_date):
    orders = Order.objects.select_related("customer").prefetch_related("items").filter(
        business_date=business_date,
        status=Order.Status.DELIVERED,
        sale__isnull=True,
    )
    created_sales = []

    with transaction.atomic():
        for order in orders:
            if not order.customer_id:
                raise ValidationError(f"El pedido #{order.id} no tiene cliente.")

            items_payload = [
                {"pizza_id": item.pizza_id, "quantity": item.quantity}
                for item in order.items.select_related("pizza").all()
            ]
            if not items_payload:
                raise ValidationError(f"El pedido #{order.id} no tiene ítems.")

            sale = create_sale(
                business_date=order.business_date,
                notes=order.notes,
                items=items_payload,
                reference_prefix=f"ORDER:{order.id}",
                customer_id=order.customer_id,
            )

            if order.total_envio is not None:
                total_envio = _to_money(order.total_envio)
                sale.total_revenue = _to_money(sale.total_revenue + total_envio)
                sale.total_profit = _to_money(sale.total_profit + total_envio)
                sale.save(update_fields=["total_revenue", "total_profit"])

            order.sale = sale
            order.save(update_fields=["sale"])
            created_sales.append(sale)

    return created_sales
