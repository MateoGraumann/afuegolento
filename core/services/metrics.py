from decimal import Decimal

from django.db.models import Avg, F, Sum, Value
from django.db.models.functions import Coalesce

from core.models import Ingredient, IngredientMovement, SaleItem


def get_profit_summary(start_date, end_date):
    queryset = SaleItem.objects.filter(
        sale__business_date__gte=start_date,
        sale__business_date__lte=end_date,
    )
    totals = queryset.aggregate(
        total_revenue=Coalesce(Sum(F("quantity") * F("applied_unit_price")), Value(Decimal("0.00"))),
        total_cost=Coalesce(Sum(F("quantity") * F("calculated_unit_cost")), Value(Decimal("0.00"))),
        total_profit=Coalesce(Sum(F("quantity") * F("calculated_unit_profit")), Value(Decimal("0.00"))),
    )
    return totals


def get_top_pizzas_by_quantity(start_date, end_date, limit=5):
    return list(
        SaleItem.objects.filter(
            sale__business_date__gte=start_date,
            sale__business_date__lte=end_date,
        )
        .values("pizza__name")
        .annotate(total_quantity=Coalesce(Sum("quantity"), Value(0)))
        .order_by("-total_quantity")[:limit]
    )


def get_top_pizzas_by_revenue(start_date, end_date, limit=5):
    return list(
        SaleItem.objects.filter(
            sale__business_date__gte=start_date,
            sale__business_date__lte=end_date,
        )
        .values("pizza__name")
        .annotate(
            total_revenue=Coalesce(
                Sum(F("quantity") * F("applied_unit_price")),
                Value(Decimal("0.00")),
            )
        )
        .order_by("-total_revenue")[:limit]
    )


def get_unit_margin_by_pizza(start_date, end_date):
    rows = list(
        SaleItem.objects.filter(
            sale__business_date__gte=start_date,
            sale__business_date__lte=end_date,
        )
        .values("pizza__name")
        .annotate(
            unit_cost=Coalesce(Avg("calculated_unit_cost"), Value(Decimal("0.00"))),
            unit_profit=Coalesce(Avg("calculated_unit_profit"), Value(Decimal("0.00"))),
        )
        .order_by("pizza__name")
    )
    for row in rows:
        unit_cost = row["unit_cost"] or Decimal("0.00")
        unit_profit = row["unit_profit"] or Decimal("0.00")
        unit_price = unit_cost + unit_profit
        if unit_price > 0:
            row["margin_percentage"] = (unit_profit / unit_price) * Decimal("100")
        else:
            row["margin_percentage"] = Decimal("0.00")
    return rows


def get_ingredient_consumption(start_date, end_date):
    return list(
        IngredientMovement.objects.filter(
            movement_type=IngredientMovement.MovementType.SALE_CONSUMPTION,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        .values("ingredient__name")
        .annotate(total_consumed=Coalesce(Sum("quantity"), Value(Decimal("0.000"))))
        .order_by("-total_consumed")
    )


def get_low_and_negative_stock():
    low_stock = list(Ingredient.objects.filter(current_stock__lt=F("min_stock")).values("id", "name", "current_stock", "min_stock"))
    negative_stock = list(Ingredient.objects.filter(current_stock__lt=0).values("id", "name", "current_stock", "min_stock"))
    return {"low_stock": low_stock, "negative_stock": negative_stock}
