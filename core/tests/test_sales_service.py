from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Customer, Ingredient, IngredientMovement, Order, OrderItem, Pizza, RecipeItem, Sale
from core.services.sales import close_sales_for_business_date, create_sale


class SalesServiceTests(TestCase):
    def setUp(self):
        self.cheese = Ingredient.objects.create(
            name="Cheese",
            unit=Ingredient.Unit.GRAM,
            unit_price=Decimal("0.02"),
            current_stock=Decimal("5000"),
            min_stock=Decimal("500"),
        )
        self.sauce = Ingredient.objects.create(
            name="Sauce",
            unit=Ingredient.Unit.GRAM,
            unit_price=Decimal("0.01"),
            current_stock=Decimal("4000"),
            min_stock=Decimal("400"),
        )
        self.pizza = Pizza.objects.create(name="Mozzarella", sale_price=Decimal("1000"))
        self.customer = Customer.objects.create(first_name="Mario", last_name="Lopez", phone="11001122")
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.cheese, quantity=Decimal("200"))
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.sauce, quantity=Decimal("100"))

    def test_create_sale_deducts_stock_and_creates_movements(self):
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

        self.cheese.refresh_from_db()
        self.sauce.refresh_from_db()
        self.assertEqual(self.cheese.current_stock, Decimal("4600"))
        self.assertEqual(self.sauce.current_stock, Decimal("3800"))

        movements = IngredientMovement.objects.filter(reference__startswith="SALE:")
        self.assertEqual(movements.count(), 2)

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
            notes="pedido",
            total_envio=Decimal("100.00"),
        )
        OrderItem.objects.create(order=order, pizza=self.pizza, quantity=2)

        created_sales = close_sales_for_business_date("2026-03-25")

        self.assertEqual(len(created_sales), 1)
        order.refresh_from_db()
        self.assertIsNotNone(order.sale)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(order.sale.total_revenue, Decimal("2100.00"))
        self.assertEqual(order.sale.total_profit, Decimal("2090.00"))

        created_again = close_sales_for_business_date("2026-03-25")
        self.assertEqual(len(created_again), 0)
