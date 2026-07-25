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
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        verbose_name="Cantidad",
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio total",
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        verbose_name="Precio unitario",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from decimal import Decimal, ROUND_HALF_UP

        quantity = Decimal(self.quantity or 0)
        total_price = Decimal(self.total_price or 0)
        if quantity > 0:
            self.unit_price = (total_price / quantity).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        else:
            self.unit_price = Decimal("0")
        super().save(*args, **kwargs)


class Pizza(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Customer(TimestampedModel):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


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
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name="sales",
        blank=True,
        null=True,
    )
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


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        IN_PROGRESS = "IN_PROGRESS", "En preparación"
        DELIVERED = "DELIVERED", "Entregado"
        CANCELLED = "CANCELLED", "Cancelado"

    created_at = models.DateTimeField(default=timezone.now)
    business_date = models.DateField()
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name="orders",
        blank=True,
        null=True,
    )
    sale = models.OneToOneField(
        Sale,
        on_delete=models.SET_NULL,
        related_name="order",
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, null=True)
    total_envio = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    direccion_envio = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Pedido {self.id} - {self.business_date}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    pizza = models.ForeignKey(Pizza, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
