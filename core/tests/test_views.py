from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import Ingredient, IngredientMovement, Pizza, RecipeItem, Sale


class ViewTests(TestCase):
    def setUp(self):
        self.ingredient = Ingredient.objects.create(
            name="Cheese",
            unit=Ingredient.Unit.GRAM,
            unit_price=Decimal("2"),
            current_stock=Decimal("2000"),
            min_stock=Decimal("300"),
        )
        self.ingredient_two = Ingredient.objects.create(
            name="Sauce",
            unit=Ingredient.Unit.GRAM,
            unit_price=Decimal("1"),
            current_stock=Decimal("1500"),
            min_stock=Decimal("250"),
        )
        self.pizza = Pizza.objects.create(name="Mozzarella", sale_price=Decimal("1000"))
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.ingredient, quantity=Decimal("200"))

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_create_real_time_sale_from_form(self):
        response = self.client.post(
            reverse("core:sale_create"),
            {
                "business_date": "2026-03-25",
                "notes": "test",
                "pizza": self.pizza.id,
                "quantity": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)

    def test_manual_stock_adjustment_creates_movement(self):
        response = self.client.post(
            reverse("core:ingredient_adjust_stock", kwargs={"pk": self.ingredient.id}),
            {
                "direction": IngredientMovement.Direction.OUT,
                "quantity": "100",
                "reference": "MANUAL:TEST",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            IngredientMovement.objects.filter(
                ingredient=self.ingredient,
                movement_type=IngredientMovement.MovementType.MANUAL_ADJUSTMENT,
            ).count(),
            1,
        )

    def test_real_time_estimate_is_rendered_before_save(self):
        response = self.client.post(
            reverse("core:sale_create"),
            {
                "business_date": "2026-03-25",
                "notes": "estimate",
                "pizza": self.pizza.id,
                "quantity": 1,
                "action": "estimate",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ganancia estimada")

    def test_dashboard_accepts_date_range_filters(self):
        response = self.client.get(
            reverse("core:dashboard"),
            {"start_date": "2026-03-01", "end_date": "2026-03-31"},
        )
        self.assertEqual(response.status_code, 200)

    def test_sale_update_and_delete(self):
        sale = Sale.objects.create(business_date="2026-03-25", notes="old")
        sale.items.create(
            pizza=self.pizza,
            quantity=1,
            applied_unit_price=Decimal("1000"),
            calculated_unit_cost=Decimal("600"),
            calculated_unit_profit=Decimal("400"),
        )
        response = self.client.post(
            reverse("core:sale_update", kwargs={"pk": sale.id}),
            {
                "business_date": "2026-03-26",
                "notes": "new",
                "pizza": self.pizza.id,
                "quantity": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(str(sale.business_date), "2026-03-26")

        delete_response = self.client.post(reverse("core:sale_delete", kwargs={"pk": sale.id}))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Sale.objects.filter(id=sale.id).exists())

    def test_ingredient_abm_edit_and_delete(self):
        response = self.client.post(
            reverse("core:ingredient_update", kwargs={"pk": self.ingredient.id}),
            {
                "name": "Queso",
                "unit": Ingredient.Unit.GRAM,
                "unit_price": "2.50",
                "current_stock": "2100",
                "min_stock": "350",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.name, "Queso")
        self.assertEqual(self.ingredient.current_stock, Decimal("2000.000"))

        delete_response = self.client.post(reverse("core:ingredient_delete", kwargs={"pk": self.ingredient.id}))
        self.assertEqual(delete_response.status_code, 302)
        self.ingredient.refresh_from_db()
        self.assertFalse(self.ingredient.is_active)

    def test_pizza_abm_edit_and_delete(self):
        response = self.client.post(
            reverse("core:pizza_update", kwargs={"pk": self.pizza.id}),
            {
                "name": "Muzza Especial",
                "sale_price": "1300",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.pizza.refresh_from_db()
        self.assertEqual(self.pizza.name, "Muzza Especial")

        delete_response = self.client.post(reverse("core:pizza_delete", kwargs={"pk": self.pizza.id}))
        self.assertEqual(delete_response.status_code, 302)
        self.pizza.refresh_from_db()
        self.assertFalse(self.pizza.is_active)

    def test_recipe_abm_create_edit_delete(self):
        response = self.client.post(
            reverse("core:recipe_create"),
            {"pizza": self.pizza.id, "ingredient": self.ingredient_two.id, "quantity": "50,000"},
        )
        self.assertEqual(response.status_code, 302)
        recipe = RecipeItem.objects.filter(pizza=self.pizza, ingredient=self.ingredient_two).first()
        self.assertIsNotNone(recipe)
        self.assertEqual(str(recipe.quantity), "50.000")

        edit_response = self.client.post(
            reverse("core:recipe_update", kwargs={"pk": recipe.id}),
            {"pizza": self.pizza.id, "ingredient": self.ingredient_two.id, "quantity": "275"},
        )
        self.assertEqual(edit_response.status_code, 302)
        recipe.refresh_from_db()
        self.assertEqual(str(recipe.quantity), "275.000")

        delete_response = self.client.post(reverse("core:recipe_delete", kwargs={"pk": recipe.id}))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(RecipeItem.objects.filter(id=recipe.id).exists())
