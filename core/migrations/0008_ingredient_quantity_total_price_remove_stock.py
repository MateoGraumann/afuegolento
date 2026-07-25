import django.core.validators
from decimal import Decimal, ROUND_HALF_UP
from django.db import migrations, models


def populate_quantity_and_total_price(apps, schema_editor):
    Ingredient = apps.get_model("core", "Ingredient")
    for ingredient in Ingredient.objects.all():
        unit_price = ingredient.unit_price or Decimal("0")
        ingredient.quantity = Decimal("1.000")
        ingredient.total_price = unit_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ingredient.save(update_fields=["quantity", "total_price"])


def recalculate_unit_price(apps, schema_editor):
    Ingredient = apps.get_model("core", "Ingredient")
    for ingredient in Ingredient.objects.all():
        quantity = ingredient.quantity or Decimal("0")
        total_price = ingredient.total_price or Decimal("0")
        if quantity > 0:
            ingredient.unit_price = (total_price / quantity).quantize(
                Decimal("0.000001"),
                rounding=ROUND_HALF_UP,
            )
        else:
            ingredient.unit_price = Decimal("0.000000")
        ingredient.save(update_fields=["unit_price"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_order_sale"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingredient",
            name="quantity",
            field=models.DecimalField(
                decimal_places=3,
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0.001)],
                verbose_name="Cantidad",
            ),
        ),
        migrations.AddField(
            model_name="ingredient",
            name="total_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Precio total",
            ),
        ),
        migrations.RunPython(populate_quantity_and_total_price, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ingredient",
            name="quantity",
            field=models.DecimalField(
                decimal_places=3,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0.001)],
                verbose_name="Cantidad",
            ),
        ),
        migrations.AlterField(
            model_name="ingredient",
            name="total_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Precio total",
            ),
        ),
        migrations.AlterField(
            model_name="ingredient",
            name="unit_price",
            field=models.DecimalField(
                decimal_places=6,
                max_digits=14,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Precio unitario",
            ),
        ),
        migrations.RunPython(recalculate_unit_price, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="ingredient",
            name="current_stock",
        ),
        migrations.RemoveField(
            model_name="ingredient",
            name="min_stock",
        ),
        migrations.DeleteModel(
            name="IngredientMovement",
        ),
    ]
