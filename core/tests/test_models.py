from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from core.models import (
    Customer,
    Ingredient,
    IngredientMovement,
    Order,
    OrderItem,
    Pizza,
    RecipeItem,
    Sale,
    SaleItem,
)


class ModelValidationTests(TestCase):
    def test_customer_requires_first_name_last_name_and_phone(self):
        customer = Customer(first_name="", last_name="", phone="")
        with self.assertRaises(ValidationError):
            customer.full_clean()

    def test_ingredient_name_is_unique(self):
        Ingredient.objects.create(
            name="Mozzarella",
            unit=Ingredient.Unit.GRAM,
            unit_price=1000,
            current_stock=10000,
            min_stock=2000,
        )
        with self.assertRaises(IntegrityError):
            Ingredient.objects.create(
                name="Mozzarella",
                unit=Ingredient.Unit.GRAM,
                unit_price=1200,
                current_stock=12000,
                min_stock=3000,
            )

    def test_recipe_item_requires_positive_quantity(self):
        ingredient = Ingredient.objects.create(
            name="Sauce",
            unit=Ingredient.Unit.GRAM,
            unit_price=10,
            current_stock=1000,
            min_stock=100,
        )
        pizza = Pizza.objects.create(name="Napolitana", sale_price=1000)
        recipe = RecipeItem(pizza=pizza, ingredient=ingredient, quantity=0)
        with self.assertRaises(ValidationError):
            recipe.full_clean()

    def test_sale_requires_business_date(self):
        sale = Sale()
        with self.assertRaises(ValidationError):
            sale.full_clean()

    def test_sale_can_reference_customer(self):
        customer = Customer.objects.create(first_name="Juan", last_name="Perez", phone="11223344")
        sale = Sale.objects.create(business_date="2026-03-25", customer=customer)
        self.assertEqual(sale.customer, customer)

    def test_sale_item_requires_positive_quantity(self):
        pizza = Pizza.objects.create(name="Muzzarella", sale_price=1200)
        sale = Sale.objects.create(business_date="2026-03-25")
        item = SaleItem(
            sale=sale,
            pizza=pizza,
            quantity=0,
            applied_unit_price=1200,
            calculated_unit_cost=700,
            calculated_unit_profit=500,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_order_allows_optional_shipping_fields(self):
        order = Order(business_date="2026-03-25")
        order.full_clean()

    def test_order_item_requires_positive_quantity(self):
        pizza = Pizza.objects.create(name="Especial", sale_price=1500)
        order = Order.objects.create(business_date="2026-03-25")
        item = OrderItem(order=order, pizza=pizza, quantity=0)
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_ingredient_movement_requires_reference(self):
        ingredient = Ingredient.objects.create(
            name="Ham",
            unit=Ingredient.Unit.GRAM,
            unit_price=15,
            current_stock=5000,
            min_stock=800,
        )
        movement = IngredientMovement(
            ingredient=ingredient,
            movement_type=IngredientMovement.MovementType.MANUAL_ADJUSTMENT,
            direction=IngredientMovement.Direction.IN,
            quantity=100,
            reference="",
        )
        with self.assertRaises(ValidationError):
            movement.full_clean()
