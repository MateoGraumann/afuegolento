from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from core.forms import IngredientAdjustStockForm, IngredientForm, PizzaForm, RecipeItemForm, SaleEntryForm
from core.models import Ingredient, IngredientMovement, Pizza, RecipeItem, Sale
from core.services.metrics import (
    get_ingredient_consumption,
    get_low_and_negative_stock,
    get_profit_summary,
    get_top_pizzas_by_quantity,
    get_top_pizzas_by_revenue,
    get_unit_margin_by_pizza,
)
from core.services.sales import create_sale, delete_sale, update_sale


def _build_estimate(pizza, quantity):
    recipe_items = RecipeItem.objects.select_related("ingredient").filter(pizza=pizza)
    if not recipe_items.exists():
        raise ValidationError("La pizza no tiene receta.")
    unit_cost = Decimal("0.00")
    for recipe_item in recipe_items:
        unit_cost += recipe_item.quantity * recipe_item.ingredient.unit_price
    unit_cost = unit_cost.quantize(Decimal("0.01"))
    unit_profit = (pizza.sale_price - unit_cost).quantize(Decimal("0.01"))
    subtotal = (pizza.sale_price * Decimal(quantity)).quantize(Decimal("0.01"))
    total_profit = (unit_profit * Decimal(quantity)).quantize(Decimal("0.01"))
    return {
        "estimated_subtotal": subtotal,
        "estimated_unit_cost": unit_cost,
        "estimated_unit_profit": unit_profit,
        "estimated_profit": total_profit,
    }


class DashboardView(View):
    template_name = "core/dashboard.html"

    def get(self, request):
        today = timezone.localdate()
        start_date = request.GET.get("start_date") or str(today)
        end_date = request.GET.get("end_date") or str(today)
        context = {
            "start_date": start_date,
            "end_date": end_date,
            "summary_today": get_profit_summary(today, today),
            "summary": get_profit_summary(start_date, end_date),
            "top_by_quantity": get_top_pizzas_by_quantity(start_date, end_date),
            "top_by_revenue": get_top_pizzas_by_revenue(start_date, end_date),
            "unit_margin": get_unit_margin_by_pizza(start_date, end_date),
            "consumption": get_ingredient_consumption(start_date, end_date),
            "stock_alerts": get_low_and_negative_stock(),
            "recent_sales": Sale.objects.order_by("-business_date", "-created_at")[:5],
        }
        return render(request, self.template_name, context)


class SaleListView(ListView):
    model = Sale
    template_name = "core/sale_list.html"
    context_object_name = "sales"

    def get_queryset(self):
        return Sale.objects.order_by("-business_date", "-created_at")


class SaleCreateView(View):
    template_name = "core/sale_form.html"

    def get(self, request):
        form = SaleEntryForm(initial={"business_date": timezone.localdate()})
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = SaleEntryForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        pizza = form.cleaned_data["pizza"]
        quantity = form.cleaned_data["quantity"]
        action = request.POST.get("action")
        if action == "estimate":
            try:
                estimate = _build_estimate(pizza, quantity)
            except ValidationError as exc:
                form.add_error(None, exc.message)
                estimate = None
            return render(
                request,
                self.template_name,
                {"form": form, "estimate": estimate},
            )

        try:
            create_sale(
                business_date=form.cleaned_data["business_date"],
                notes=form.cleaned_data["notes"],
                items=[{"pizza_id": pizza.id, "quantity": quantity}],
                reference_prefix="SALE",
            )
            messages.success(request, "Venta registrada.")
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return render(request, self.template_name, {"form": form})
        return redirect("core:sale_list")


class SaleUpdateView(View):
    template_name = "core/sale_form.html"

    def get(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        sale_item = sale.items.select_related("pizza").first()
        initial = {"business_date": sale.business_date, "notes": sale.notes}
        if sale_item:
            initial["pizza"] = sale_item.pizza
            initial["quantity"] = sale_item.quantity
        form = SaleEntryForm(initial=initial)
        return render(request, self.template_name, {"form": form, "sale": sale})

    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        form = SaleEntryForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "sale": sale})

        try:
            update_sale(
                sale=sale,
                business_date=form.cleaned_data["business_date"],
                notes=form.cleaned_data["notes"],
                items=[
                    {
                        "pizza_id": form.cleaned_data["pizza"].id,
                        "quantity": form.cleaned_data["quantity"],
                    }
                ],
            )
            messages.success(request, "Venta actualizada.")
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return render(request, self.template_name, {"form": form, "sale": sale})
        return redirect("core:sale_list")


class SaleDeleteView(View):
    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        delete_sale(sale)
        messages.success(request, "Venta eliminada.")
        return redirect("core:sale_list")


class IngredientListView(ListView):
    model = Ingredient
    template_name = "core/ingredient_list.html"
    context_object_name = "ingredients"


class IngredientCreateView(View):
    template_name = "core/ingredient_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": IngredientForm()})

    def post(self, request):
        form = IngredientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:ingredient_list")
        return render(request, self.template_name, {"form": form})


class IngredientUpdateView(View):
    template_name = "core/ingredient_form.html"

    def get(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        return render(
            request,
            self.template_name,
            {"form": IngredientForm(instance=ingredient, allow_stock_edit=False), "ingredient": ingredient},
        )

    def post(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        form = IngredientForm(request.POST, instance=ingredient, allow_stock_edit=False)
        if form.is_valid():
            form.save()
            messages.success(request, "Insumo actualizado.")
            return redirect("core:ingredient_list")
        return render(request, self.template_name, {"form": form, "ingredient": ingredient})


class IngredientDeleteView(View):
    def post(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        ingredient.is_active = False
        ingredient.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Insumo dado de baja.")
        return redirect("core:ingredient_list")


class PizzaListView(ListView):
    model = Pizza
    template_name = "core/pizza_list.html"
    context_object_name = "pizzas"


class PizzaCreateView(View):
    template_name = "core/pizza_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PizzaForm()})

    def post(self, request):
        form = PizzaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:pizza_list")
        return render(request, self.template_name, {"form": form})


class PizzaUpdateView(View):
    template_name = "core/pizza_form.html"

    def get(self, request, pk):
        pizza = get_object_or_404(Pizza, pk=pk)
        return render(request, self.template_name, {"form": PizzaForm(instance=pizza), "pizza": pizza})

    def post(self, request, pk):
        pizza = get_object_or_404(Pizza, pk=pk)
        form = PizzaForm(request.POST, instance=pizza)
        if form.is_valid():
            form.save()
            messages.success(request, "Pizza actualizada.")
            return redirect("core:pizza_list")
        return render(request, self.template_name, {"form": form, "pizza": pizza})


class PizzaDeleteView(View):
    def post(self, request, pk):
        pizza = get_object_or_404(Pizza, pk=pk)
        pizza.is_active = False
        pizza.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Pizza dada de baja.")
        return redirect("core:pizza_list")


class IngredientAdjustStockView(View):
    template_name = "core/ingredient_adjust_stock_form.html"

    def get(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        return render(request, self.template_name, {"ingredient": ingredient, "form": IngredientAdjustStockForm()})

    def post(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        form = IngredientAdjustStockForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"ingredient": ingredient, "form": form})

        direction = form.cleaned_data["direction"]
        quantity = form.cleaned_data["quantity"]
        reference = form.cleaned_data["reference"]

        with transaction.atomic():
            if direction == IngredientMovement.Direction.IN:
                ingredient.current_stock = ingredient.current_stock + quantity
            else:
                ingredient.current_stock = ingredient.current_stock - quantity
            ingredient.save(update_fields=["current_stock", "updated_at"])
            movement = IngredientMovement(
                ingredient=ingredient,
                movement_type=IngredientMovement.MovementType.MANUAL_ADJUSTMENT,
                direction=direction,
                quantity=quantity,
                reference=reference,
            )
            movement.full_clean()
            movement.save()
        return redirect("core:ingredient_list")


class RecipeItemListView(ListView):
    model = RecipeItem
    template_name = "core/recipe_list.html"
    context_object_name = "recipes"

    def get_queryset(self):
        return RecipeItem.objects.select_related("pizza", "ingredient").order_by("pizza__name", "ingredient__name")


class RecipeItemCreateView(View):
    template_name = "core/recipe_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": RecipeItemForm()})

    def post(self, request):
        form = RecipeItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Receta creada.")
            return redirect("core:recipe_list")
        return render(request, self.template_name, {"form": form})


class RecipeItemUpdateView(View):
    template_name = "core/recipe_form.html"

    def get(self, request, pk):
        recipe = get_object_or_404(RecipeItem, pk=pk)
        return render(request, self.template_name, {"form": RecipeItemForm(instance=recipe), "recipe": recipe})

    def post(self, request, pk):
        recipe = get_object_or_404(RecipeItem, pk=pk)
        form = RecipeItemForm(request.POST, instance=recipe)
        if form.is_valid():
            form.save()
            messages.success(request, "Receta actualizada.")
            return redirect("core:recipe_list")
        return render(request, self.template_name, {"form": form, "recipe": recipe})


class RecipeItemDeleteView(View):
    def post(self, request, pk):
        recipe = get_object_or_404(RecipeItem, pk=pk)
        recipe.delete()
        messages.success(request, "Receta eliminada.")
        return redirect("core:recipe_list")
