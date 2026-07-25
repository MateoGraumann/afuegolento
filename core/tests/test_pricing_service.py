from decimal import Decimal

from django.test import TestCase

from core.models import Ingredient, Pizza, RecipeItem, Sale
from core.services.pricing import SimulationParams, simulate_pricing, suggest_pizza_prices


class PricingServiceTests(TestCase):
    def setUp(self):
        self.cheese = Ingredient.objects.create(
            name="Mozzarella",
            unit=Ingredient.Unit.GRAM,
            quantity=Decimal("1"),
            total_price=Decimal("2"),
        )
        self.sauce = Ingredient.objects.create(
            name="Salsa",
            unit=Ingredient.Unit.GRAM,
            quantity=Decimal("1"),
            total_price=Decimal("1"),
        )
        self.pizza = Pizza.objects.create(name="Muzza", sale_price=Decimal("1000"))
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.cheese, quantity=Decimal("200"))
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.sauce, quantity=Decimal("50"))

    def test_fixed_overhead_formula_and_summary(self):
        result = simulate_pricing(SimulationParams(overhead_fixed="900", margin_pct="50"))
        row = result["rows"][0]

        # recipe = 200*2 + 50*1 = 450; total = 1350; ideal = 2700
        self.assertEqual(row["recipe_cost"], Decimal("450.00"))
        self.assertEqual(row["overhead"], Decimal("900.00"))
        self.assertEqual(row["total_cost"], Decimal("1350.00"))
        self.assertEqual(row["ideal_price"], Decimal("2700.00"))
        self.assertEqual(row["profit"], Decimal("-350.00"))
        self.assertEqual(row["difference"], Decimal("-1700.00"))
        self.assertEqual(row["status"], "below")
        self.assertEqual(result["summary"]["below_target_count"], 1)
        self.assertEqual(result["summary"]["avg_total_cost"], Decimal("1350.00"))

    def test_excellent_status_when_margin_well_above_target(self):
        self.pizza.sale_price = Decimal("8000")
        self.pizza.save(update_fields=["sale_price"])
        result = simulate_pricing(SimulationParams(overhead_fixed="900", margin_pct="50"))
        row = result["rows"][0]
        self.assertEqual(row["status"], "excellent")

    def test_ingredient_price_override_extensibility(self):
        params = SimulationParams(
            overhead_fixed="0",
            margin_pct="50",
            ingredient_price_overrides={self.cheese.id: Decimal("4")},
        )
        result = simulate_pricing(params)
        row = result["rows"][0]
        # recipe = 200*4 + 50*1 = 850
        self.assertEqual(row["recipe_cost"], Decimal("850.00"))
        cheese_line = next(item for item in row["breakdown"] if item["label"] == "Mozzarella")
        self.assertEqual(cheese_line["amount"], Decimal("800.00"))

    def test_suggest_pizza_prices_compat_without_side_effects(self):
        sale_count = Sale.objects.count()
        result = suggest_pizza_prices(overhead_fixed="900", margin_pct="50")
        self.assertEqual(result["rows"][0]["total_cost"], Decimal("1350.00"))
        self.assertEqual(Sale.objects.count(), sale_count)

    def test_breakdown_includes_overhead_share(self):
        result = simulate_pricing(SimulationParams(overhead_fixed="450", margin_pct="50"))
        labels = [item["label"] for item in result["rows"][0]["breakdown"]]
        self.assertIn("Overhead", labels)
        self.assertIn("Mozzarella", labels)
