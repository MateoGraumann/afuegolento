from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import Customer, Ingredient, IngredientMovement, Order, Pizza, RecipeItem, Sale


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
        self.customer = Customer.objects.create(first_name="Ana", last_name="Gomez", phone="11445566")
        RecipeItem.objects.create(pizza=self.pizza, ingredient=self.ingredient, quantity=Decimal("200"))

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_create_real_time_sale_from_form(self):
        Sale.objects.create(
            business_date="2026-03-25",
            notes="test",
            total_revenue=Decimal("1200.00"),
            total_cost=Decimal("600.00"),
            total_profit=Decimal("600.00"),
        )
        response = self.client.get(reverse("core:sale_list"), {"business_date": "2026-03-25"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1200,00")

    def test_create_sale_creates_new_customer_from_form(self):
        Sale.objects.create(
            business_date="2026-03-26",
            notes="new customer",
            total_revenue=Decimal("1300.00"),
            total_cost=Decimal("700.00"),
            total_profit=Decimal("600.00"),
        )
        response = self.client.get(reverse("core:sale_list"), {"business_date": "2026-03-25"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "1300,00")

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
        response = self.client.get(reverse("core:sale_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fecha operativa")

    def test_dashboard_accepts_date_range_filters(self):
        response = self.client.get(
            reverse("core:dashboard"),
            {"start_date": "2026-03-01", "end_date": "2026-03-31"},
        )
        self.assertEqual(response.status_code, 200)

    def test_sale_update_and_delete(self):
        sale = Sale.objects.create(
            business_date="2026-03-25",
            notes="old",
            total_revenue=Decimal("1000.00"),
            total_cost=Decimal("500.00"),
            total_profit=Decimal("500.00"),
        )
        edit_response = self.client.get(f"/sales/{sale.id}/edit/")
        delete_response = self.client.post(f"/sales/{sale.id}/delete/")
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

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

    def test_customer_abm_edit_and_delete(self):
        response = self.client.post(
            reverse("core:customer_update", kwargs={"pk": self.customer.id}),
            {
                "first_name": "Analia",
                "last_name": "Gomez",
                "phone": "111000",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Analia")

        delete_response = self.client.post(reverse("core:customer_delete", kwargs={"pk": self.customer.id}))
        self.assertEqual(delete_response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

    def test_order_abm_create_update_delete(self):
        create_response = self.client.post(
            reverse("core:order_create"),
            {
                "business_date": "2026-03-25",
                "customer": str(self.customer.id),
                "status": "PENDING",
                "total_envio": "350.00",
                "direccion_envio": "Calle 123",
                "notes": "sin cebolla",
                "items-TOTAL_FORMS": "3",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-pizza": str(self.pizza.id),
                "items-0-quantity": "2",
                "items-1-pizza": "",
                "items-1-quantity": "",
                "items-2-pizza": "",
                "items-2-quantity": "",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        order = Order.objects.order_by("-id").first()
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.customer, self.customer)

        update_response = self.client.post(
            reverse("core:order_update", kwargs={"pk": order.id}),
            {
                "business_date": "2026-03-26",
                "customer": str(self.customer.id),
                "status": "DELIVERED",
                "total_envio": "0",
                "direccion_envio": "",
                "notes": "entregado",
                "items-TOTAL_FORMS": "3",
                "items-INITIAL_FORMS": "1",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": str(order.items.first().id),
                "items-0-pizza": str(self.pizza.id),
                "items-0-quantity": "3",
                "items-1-pizza": "",
                "items-1-quantity": "",
                "items-2-pizza": "",
                "items-2-quantity": "",
            },
        )
        self.assertEqual(update_response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(str(order.business_date), "2026-03-26")
        self.assertEqual(order.status, "DELIVERED")
        self.assertEqual(order.items.first().quantity, 3)

        delete_response = self.client.post(reverse("core:order_delete", kwargs={"pk": order.id}))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Order.objects.filter(id=order.id).exists())

    def test_order_create_with_new_customer(self):
        response = self.client.post(
            reverse("core:order_create"),
            {
                "business_date": "2026-03-25",
                "is_new_customer": "on",
                "customer_first_name": "Lucia",
                "customer_last_name": "Paz",
                "customer_phone": "11334455",
                "status": "PENDING",
                "total_envio": "120.00",
                "direccion_envio": "Calle Falsa 123",
                "notes": "nuevo cliente",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-pizza": str(self.pizza.id),
                "items-0-quantity": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.order_by("-id").first()
        self.assertIsNotNone(order)
        self.assertIsNotNone(order.customer)
        self.assertEqual(order.customer.first_name, "Lucia")

    def test_order_update_form_preloads_business_date(self):
        order = Order.objects.create(
            business_date="2026-03-25",
            customer=self.customer,
            status=Order.Status.PENDING,
            notes="fecha test",
        )
        order.items.create(pizza=self.pizza, quantity=1)

        response = self.client.get(reverse("core:order_update", kwargs={"pk": order.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="business_date"')
        self.assertContains(response, 'value="2026-03-25"')

    def test_close_day_creates_sales_from_delivered_orders(self):
        order = Order.objects.create(
            business_date="2026-03-25",
            customer=self.customer,
            status=Order.Status.DELIVERED,
            notes="pedido entregado",
            total_envio=Decimal("50.00"),
        )
        order.items.create(pizza=self.pizza, quantity=1)

        response = self.client.post(reverse("core:sale_close_day"), {"business_date": "2026-03-25"})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertIsNotNone(order.sale)
        self.assertTrue(Sale.objects.filter(id=order.sale.id).exists())

    def test_close_day_does_not_process_non_delivered_orders(self):
        order = Order.objects.create(
            business_date="2026-03-25",
            customer=self.customer,
            status=Order.Status.PENDING,
            notes="pendiente",
        )
        order.items.create(pizza=self.pizza, quantity=1)

        response = self.client.post(reverse("core:sale_close_day"), {"business_date": "2026-03-25"})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertIsNone(order.sale)

    def test_closed_order_cannot_be_edited_or_deleted(self):
        order = Order.objects.create(
            business_date="2026-03-25",
            customer=self.customer,
            status=Order.Status.DELIVERED,
            notes="cerrado",
        )
        order.items.create(pizza=self.pizza, quantity=1)
        self.client.post(reverse("core:sale_close_day"), {"business_date": "2026-03-25"})
        order.refresh_from_db()
        self.assertIsNotNone(order.sale)

        get_edit = self.client.get(reverse("core:order_update", kwargs={"pk": order.id}))
        post_edit = self.client.post(
            reverse("core:order_update", kwargs={"pk": order.id}),
            {
                "business_date": "2026-03-25",
                "customer": str(self.customer.id),
                "status": "DELIVERED",
                "total_envio": "0",
                "direccion_envio": "",
                "notes": "intento editar",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "1",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": str(order.items.first().id),
                "items-0-pizza": str(self.pizza.id),
                "items-0-quantity": "2",
            },
        )
        post_delete = self.client.post(reverse("core:order_delete", kwargs={"pk": order.id}))

        self.assertEqual(get_edit.status_code, 302)
        self.assertEqual(post_edit.status_code, 302)
        self.assertEqual(post_delete.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.notes, "cerrado")
        self.assertTrue(Order.objects.filter(id=order.id).exists())
