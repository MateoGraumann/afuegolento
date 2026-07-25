"""Simulador de precios — lógica desacoplada de la UI.

Arquitectura extensible vía SimulationParams:
- overhead_fixed / margin_pct: controles actuales
- ingredient_price_overrides: simular subas de insumos (futuro)
- sale_price_overrides / discount_pct: promociones (futuro)

Los costos reales de venta (close day) NO usan este módulo.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Prefetch

from core.models import Pizza, RecipeItem

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.01")

DEFAULT_OVERHEAD_FIXED = Decimal("900")
DEFAULT_MARGIN_PCT = Decimal("50")
MARGIN_TOLERANCE_PCT = Decimal("2")
EXCELLENT_MARGIN_BUFFER_PCT = Decimal("5")

# Compatibilidad con imports antiguos
DEFAULT_OVERHEAD_PCT = DEFAULT_OVERHEAD_FIXED


class SimulationParams:
    """Parámetros de una simulación de rentabilidad.

    Extensible: agregar overrides no requiere cambiar la UI de una vez.
    """

    def __init__(
        self,
        overhead_fixed=None,
        margin_pct=None,
        ingredient_price_overrides=None,
        sale_price_overrides=None,
        discount_pct=None,
    ):
        self.overhead_fixed = _normalize_money(overhead_fixed, DEFAULT_OVERHEAD_FIXED, min_value=Decimal("0"))
        self.margin_pct = _normalize_margin(margin_pct, DEFAULT_MARGIN_PCT)
        self.ingredient_price_overrides = ingredient_price_overrides or {}
        self.sale_price_overrides = sale_price_overrides or {}
        self.discount_pct = _to_decimal(discount_pct, Decimal("0"))
        if self.discount_pct < 0:
            self.discount_pct = Decimal("0")
        if self.discount_pct >= 100:
            self.discount_pct = Decimal("0")


def _to_decimal(value, default):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _normalize_money(value, default, min_value=None):
    amount = _to_decimal(value, default)
    if min_value is not None and amount < min_value:
        return default
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _normalize_margin(value, default):
    margin = _to_decimal(value, default)
    if margin <= 0 or margin >= 100:
        return default
    return margin.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _to_money(value):
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _to_pct(value):
    return Decimal(value).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def resolve_ingredient_unit_price(ingredient, params):
    override = params.ingredient_price_overrides.get(ingredient.id)
    if override is not None:
        return _to_money(override)
    return _to_money(ingredient.unit_price)


def resolve_sale_price(pizza, params):
    override = params.sale_price_overrides.get(pizza.id)
    price = _to_money(override if override is not None else pizza.sale_price)
    if params.discount_pct > 0:
        price = _to_money(price * (Decimal("1") - params.discount_pct / Decimal("100")))
    return price


def build_recipe_lines(pizza, params):
    lines = []
    for recipe_item in pizza.recipe_items.all():
        ingredient = recipe_item.ingredient
        if not ingredient.is_active:
            continue
        unit_price = resolve_ingredient_unit_price(ingredient, params)
        line_cost = _to_money(recipe_item.quantity * unit_price)
        lines.append(
            {
                "ingredient_id": ingredient.id,
                "name": ingredient.name,
                "quantity": recipe_item.quantity,
                "unit_price": unit_price,
                "line_cost": line_cost,
            }
        )
    return lines


def calculate_recipe_cost_from_lines(lines):
    total = Decimal("0")
    for line in lines:
        total += line["line_cost"]
    return _to_money(total)


def calculate_recipe_cost(pizza, params=None):
    params = params or SimulationParams()
    return calculate_recipe_cost_from_lines(build_recipe_lines(pizza, params))


def classify_margin_status(real_margin_pct, target_margin_pct):
    if real_margin_pct is None:
        return "below", "Debajo del margen"
    if real_margin_pct < target_margin_pct - MARGIN_TOLERANCE_PCT:
        return "below", "Debajo del margen"
    if real_margin_pct >= target_margin_pct + EXCELLENT_MARGIN_BUFFER_PCT:
        return "excellent", "Excelente"
    return "on_target", "Dentro del objetivo"


def build_cost_breakdown(lines, overhead_fixed, total_cost):
    breakdown = []
    for line in lines:
        share = Decimal("0")
        if total_cost > 0:
            share = _to_pct((line["line_cost"] / total_cost) * Decimal("100"))
        breakdown.append(
            {
                "key": f"ingredient-{line['ingredient_id']}",
                "label": line["name"],
                "amount": line["line_cost"],
                "share_pct": share,
                "kind": "ingredient",
            }
        )

    overhead_share = Decimal("0")
    if total_cost > 0:
        overhead_share = _to_pct((overhead_fixed / total_cost) * Decimal("100"))
    breakdown.append(
        {
            "key": "overhead",
            "label": "Overhead",
            "amount": overhead_fixed,
            "share_pct": overhead_share,
            "kind": "overhead",
        }
    )
    breakdown.sort(key=lambda item: item["amount"], reverse=True)
    return breakdown


def evaluate_pizza(pizza, params):
    lines = build_recipe_lines(pizza, params)
    recipe_cost = calculate_recipe_cost_from_lines(lines)
    overhead = params.overhead_fixed
    total_cost = _to_money(recipe_cost + overhead)
    margin_factor = Decimal("1") - (params.margin_pct / Decimal("100"))
    ideal_price = _to_money(total_cost / margin_factor) if margin_factor > 0 else Decimal("0.00")
    current_price = resolve_sale_price(pizza, params)
    profit = _to_money(current_price - total_cost)
    difference = _to_money(current_price - ideal_price)

    if current_price > 0:
        real_margin_pct = _to_pct((profit / current_price) * Decimal("100"))
    else:
        real_margin_pct = None

    status, status_label = classify_margin_status(real_margin_pct, params.margin_pct)
    breakdown = build_cost_breakdown(lines, overhead, total_cost)

    return {
        "pizza": pizza,
        "pizza_id": pizza.id,
        "pizza_name": pizza.name,
        "lines": lines,
        "recipe_cost": recipe_cost,
        "overhead": overhead,
        "total_cost": total_cost,
        "cost_with_overhead": total_cost,  # alias retrocompatible
        "current_price": current_price,
        "ideal_price": ideal_price,
        "profit": profit,
        "real_margin_pct": real_margin_pct,
        "difference": difference,
        "status": status,
        "status_label": status_label,
        "breakdown": breakdown,
    }


def build_summary(rows):
    if not rows:
        return {
            "avg_total_cost": Decimal("0.00"),
            "avg_current_price": Decimal("0.00"),
            "avg_real_margin_pct": Decimal("0.00"),
            "below_target_count": 0,
            "product_count": 0,
        }

    count = len(rows)
    avg_total_cost = _to_money(sum((row["total_cost"] for row in rows), Decimal("0")) / count)
    avg_current_price = _to_money(sum((row["current_price"] for row in rows), Decimal("0")) / count)
    margins = [row["real_margin_pct"] for row in rows if row["real_margin_pct"] is not None]
    if margins:
        avg_real_margin_pct = _to_pct(sum(margins, Decimal("0")) / len(margins))
    else:
        avg_real_margin_pct = Decimal("0.00")
    below_target_count = sum(1 for row in rows if row["status"] == "below")

    return {
        "avg_total_cost": avg_total_cost,
        "avg_current_price": avg_current_price,
        "avg_real_margin_pct": avg_real_margin_pct,
        "below_target_count": below_target_count,
        "product_count": count,
    }


def _active_pizzas_queryset():
    recipe_qs = RecipeItem.objects.select_related("ingredient").filter(ingredient__is_active=True)
    return (
        Pizza.objects.filter(is_active=True)
        .prefetch_related(Prefetch("recipe_items", queryset=recipe_qs))
        .order_by("name")
    )


def simulate_pricing(params=None):
    """Punto de entrada principal del simulador."""
    params = params or SimulationParams()
    rows = [evaluate_pizza(pizza, params) for pizza in _active_pizzas_queryset()]
    return {
        "params": params,
        "overhead_fixed": params.overhead_fixed,
        "margin_pct": params.margin_pct,
        "rows": rows,
        "summary": build_summary(rows),
    }


def build_simulator_payload(params=None):
    """Payload JSON para simulación reactiva en el cliente."""
    result = simulate_pricing(params)
    pizzas = []
    for row in result["rows"]:
        pizzas.append(
            {
                "id": row["pizza_id"],
                "name": row["pizza_name"],
                "sale_price": str(row["current_price"]),
                "lines": [
                    {
                        "ingredient_id": line["ingredient_id"],
                        "name": line["name"],
                        "quantity": str(line["quantity"]),
                        "unit_price": str(line["unit_price"]),
                    }
                    for line in row["lines"]
                ],
            }
        )
    return {
        "defaults": {
            "overhead_fixed": str(result["overhead_fixed"]),
            "margin_pct": str(result["margin_pct"]),
        },
        "pizzas": pizzas,
        "meta": {
            "margin_tolerance_pct": str(MARGIN_TOLERANCE_PCT),
            "excellent_margin_buffer_pct": str(EXCELLENT_MARGIN_BUFFER_PCT),
        },
    }


def suggest_pizza_prices(overhead_pct=None, margin_pct=None, overhead_fixed=None):
    """Compatibilidad: acepta overhead fijo (preferido) o el nombre histórico overhead_pct.

    Si se pasa overhead_pct sin overhead_fixed, se interpreta como monto fijo
    (el simulador ya no usa porcentaje de overhead).
    """
    fixed = overhead_fixed if overhead_fixed is not None else overhead_pct
    params = SimulationParams(overhead_fixed=fixed, margin_pct=margin_pct)
    return simulate_pricing(params)
