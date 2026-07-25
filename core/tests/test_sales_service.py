from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Customer, Ingredient, Order, OrderItem, Pizza, RecipeItem, Sale
from core.services.sales import close_sales_for_business_date, create_sale


def _ingredient(name, unit, unit_price):
    """Crea insumo con precio unitario objetivo vía cantidad=1."""
    return Ingredient.objects.create(
        name=name,
        unit=unit,
        quantity=Decimal("1"),
        total_price=Decimal(unit_price),
    )


class SalesServiceTests(TestCase):
    def setUp(self):
        self.cheese = _ingredient("Cheese", Ingredient.Unit.GRAM, "0.02")
        self.sauce = _ingredient("Sauce", Ingredient.Unit.GRAM, "0.01")
        self.pizza = Pizza.objects.create(name="Mozzarella", sale_price=Decimal("1000"))
        self.customer = Customer.objects.create(first_name="Mario", last_name="Lopez", phone="11001122")
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.cheese, quantity=Decimal("200"))
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.sauce, quantity=Decimal("100"))

    def test_create_sale_calculates_cost_without_stock(self):
        sale = create_sale(
            business_date="2026-03-25",
            notes="Rush hour",
            items=[{"pizza_id": self.pizza.id, "quantity": 2}],
            reference_prefix="SALE",
            customer_id=self.customer.id,
        )

        self.assertEqual(sale.items.count(), 1)
        sale_item = sale.items.first()
        self.assertEqual(sale_item.applied_unit_price, Decimal("1000"))
        self.assertEqual(sale_item.calculated_unit_cost, Decimal("5.00"))
        self.assertEqual(sale_item.calculated_unit_profit, Decimal("995.00"))
        self.assertEqual(sale.total_revenue, Decimal("2000.00"))
        self.assertEqual(sale.total_cost, Decimal("10.00"))
        self.assertEqual(sale.total_profit, Decimal("1990.00"))

    def test_create_sale_fails_without_recipe(self):
        empty_recipe_pizza = Pizza.objects.create(name="No Recipe", sale_price=Decimal("500"))
        with self.assertRaises(ValidationError):
            create_sale(
                business_date="2026-03-25",
                notes="",
                items=[{"pizza_id": empty_recipe_pizza.id, "quantity": 1}],
                reference_prefix="SALE",
                customer_id=self.customer.id,
            )

    def test_create_sale_fails_with_inactive_pizza(self):
        self.pizza.is_active = False
        self.pizza.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            create_sale(
                business_date="2026-03-25",
                notes="",
                items=[{"pizza_id": self.pizza.id, "quantity": 1}],
                reference_prefix="SALE",
                customer_id=self.customer.id,
            )

    def test_create_sale_fails_with_inactive_ingredient(self):
        self.cheese.is_active = False
        self.cheese.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            create_sale(
                business_date="2026-03-25",
                notes="",
                items=[{"pizza_id": self.pizza.id, "quantity": 1}],
                reference_prefix="SALE",
                customer_id=self.customer.id,
            )

    def test_close_sales_for_business_date_from_delivered_orders(self):
        order = Order.objects.create(
            business_date="2026-03-25",
            customer=self.customer,
            status=Order.Status.DELIVERED,
            notes="delivered",
            total_envio=Decimal("50.00"),
        )
        OrderItem.objects.create(order=order, pizza=self.pizza, quantity=1)

        created = close_sales_for_business_date("2026-03-25")
        self.assertEqual(len(created), 1)
        order.refresh_from_db()
        self.assertIsNotNone(order.sale)
        self.assertEqual(order.sale.total_revenue, Decimal("1050.00"))
