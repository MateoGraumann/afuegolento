from decimal import Decimal
from django.test import TestCase

from core.models import Ingredient, Pizza, RecipeItem
from core.services.metrics import (
    get_ingredient_consumption,
    get_low_and_negative_stock,
    get_profit_summary,
    get_top_pizzas_by_quantity,
    get_top_pizzas_by_revenue,
    get_unit_margin_by_pizza,
)
from core.services.sales import create_sale


class MetricsServiceTests(TestCase):
    def setUp(self):
        self.cheese = Ingredient.objects.create(
            name="Cheese",
            unit=Ingredient.Unit.GRAM,
            unit_price=Decimal("2"),
            current_stock=Decimal("2000"),
            min_stock=Decimal("300"),
        )
        self.sauce = Ingredient.objects.create(
            name="Sauce",
            unit=Ingredient.Unit.GRAM,
            unit_price=Decimal("1"),
            current_stock=Decimal("1500"),
            min_stock=Decimal("250"),
        )
        self.mozza = Pizza.objects.create(name="Mozzarella", sale_price=Decimal("1000"))
        self.fugazza = Pizza.objects.create(name="Fugazza", sale_price=Decimal("1200"))
        RecipeItem.objects.create(pizza=self.mozza, ingredient=self.cheese, quantity=Decimal("200"))
        RecipeItem.objects.create(pizza=self.mozza, ingredient=self.sauce, quantity=Decimal("100"))
        RecipeItem.objects.create(pizza=self.fugazza, ingredient=self.cheese, quantity=Decimal("250"))
        RecipeItem.objects.create(pizza=self.fugazza, ingredient=self.sauce, quantity=Decimal("100"))

    def test_profit_summary_uses_business_date_and_controlled_case(self):
        create_sale(
            business_date="2026-03-25",
            notes="Morning",
            items=[{"pizza_id": self.mozza.id, "quantity": 3}],
        )
        summary = get_profit_summary("2026-03-25", "2026-03-25")
        # controlled case: 1000 price, 500 unit cost, qty 3 => 1500 total profit
        self.assertEqual(summary["total_profit"], Decimal("1500.00"))

    def test_daily_close_snapshot_consistency(self):
        create_sale(
            business_date="2026-03-25",
            notes="Close",
            items=[{"pizza_id": self.fugazza.id, "quantity": 2}],
        )
        self.fugazza.sale_price = Decimal("3000")
        self.fugazza.save(update_fields=["sale_price"])

        summary = get_profit_summary("2026-03-25", "2026-03-25")
        self.assertEqual(summary["total_revenue"], Decimal("2400.00"))

    def test_top_pizzas_by_quantity_and_revenue(self):
        create_sale(
            business_date="2026-03-25",
            notes="Service",
            items=[
                {"pizza_id": self.mozza.id, "quantity": 5},
                {"pizza_id": self.fugazza.id, "quantity": 2},
            ],
        )
        top_qty = get_top_pizzas_by_quantity("2026-03-25", "2026-03-25")
        top_rev = get_top_pizzas_by_revenue("2026-03-25", "2026-03-25")
        self.assertEqual(top_qty[0]["pizza__name"], "Mozzarella")
        self.assertEqual(top_rev[0]["pizza__name"], "Mozzarella")

    def test_consumption_and_low_stock_alerts(self):
        create_sale(
            business_date="2026-03-25",
            notes="Service",
            items=[{"pizza_id": self.mozza.id, "quantity": 8}],
        )
        consumption = get_ingredient_consumption("2026-03-25", "2026-03-25")
        self.assertTrue(any(row["ingredient__name"] == "Cheese" for row in consumption))

        alerts = get_low_and_negative_stock()
        self.assertIn("low_stock", alerts)
        self.assertIn("negative_stock", alerts)

    def test_unit_margin_by_pizza(self):
        create_sale(
            business_date="2026-03-25",
            notes="Service",
            items=[{"pizza_id": self.mozza.id, "quantity": 1}],
        )
        rows = get_unit_margin_by_pizza("2026-03-25", "2026-03-25")
        self.assertEqual(rows[0]["pizza__name"], "Mozzarella")
        self.assertEqual(rows[0]["margin_percentage"], Decimal("50.0"))
