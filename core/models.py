from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Ingredient(TimestampedModel):
    class Unit(models.TextChoices):
        GRAM = "g", "Gramo"
        MILLILITER = "ml", "Mililitro"
        UNIT = "un", "Unidad"

    name = models.CharField(max_length=120, unique=True)
    unit = models.CharField(max_length=2, choices=Unit.choices)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0)])
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Pizza(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class RecipeItem(models.Model):
    pizza = models.ForeignKey(Pizza, on_delete=models.CASCADE, related_name="recipe_items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="recipe_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0.001)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pizza", "ingredient"], name="uniq_recipe_item"),
        ]

    def clean(self):
        super().clean()
        if self.ingredient_id and self.ingredient.unit not in dict(Ingredient.Unit.choices):
            raise ValidationError({"ingredient": "Ingredient unit is not valid for recipe usage."})


class Sale(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    business_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Venta {self.id} - {self.business_date}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    pizza = models.ForeignKey(Pizza, on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    applied_unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    calculated_unit_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    calculated_unit_profit = models.DecimalField(max_digits=12, decimal_places=2)


class IngredientMovement(models.Model):
    class MovementType(models.TextChoices):
        SALE_CONSUMPTION = "SALE_CONSUMPTION", "Consumo por venta"
        MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT", "Ajuste manual"

    class Direction(models.TextChoices):
        IN = "IN", "Entrada"
        OUT = "OUT", "Salida"

    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    direction = models.CharField(max_length=3, choices=Direction.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0.001)])
    created_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=120)

    def clean(self):
        super().clean()
        if not self.reference or not self.reference.strip():
            raise ValidationError({"reference": "La referencia es obligatoria."})
        if self.movement_type == self.MovementType.SALE_CONSUMPTION and self.direction != self.Direction.OUT:
            raise ValidationError({"direction": "SALE_CONSUMPTION debe usar dirección OUT."})

    def __str__(self):
        return f"{self.ingredient.name} {self.movement_type} {self.quantity}"
