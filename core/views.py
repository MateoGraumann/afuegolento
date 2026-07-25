import json
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import inlineformset_factory
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from core.forms import (
    CustomerForm,
    IngredientForm,
    OrderForm,
    OrderItemForm,
    PizzaForm,
    RecipeItemForm,
)
from core.models import Customer, Ingredient, Order, OrderItem, Pizza, RecipeItem, Sale
from core.services.metrics import (
    get_profit_summary,
    get_top_pizzas_by_quantity,
    get_top_pizzas_by_revenue,
    get_unit_margin_by_pizza,
)
from core.services.orders import change_order_status
from core.services.pricing import (
    DEFAULT_MARGIN_PCT,
    DEFAULT_OVERHEAD_FIXED,
    SimulationParams,
    build_simulator_payload,
    simulate_pricing,
)
from core.services.sales import close_sales_for_business_date


class DashboardView(View):
    template_name = "core/dashboard.html"

    def get(self, request):
        today = timezone.localdate()
        start_date = request.GET.get("start_date") or str(today)
        end_date = request.GET.get("end_date") or str(today)
        context = {
            "today": today,
            "start_date": start_date,
            "end_date": end_date,
            "preset_week_start": today - timedelta(days=6),
            "preset_month_start": today.replace(day=1),
            "summary": get_profit_summary(start_date, end_date),
            "top_by_quantity": get_top_pizzas_by_quantity(start_date, end_date),
            "top_by_revenue": get_top_pizzas_by_revenue(start_date, end_date),
            "unit_margin": get_unit_margin_by_pizza(start_date, end_date),
        }
        return render(request, self.template_name, context)


class SaleListView(View):
    template_name = "core/sale_list.html"

    def get(self, request):
        today = timezone.localdate()
        start_date = request.GET.get("start_date") or str(today)
        end_date = request.GET.get("end_date") or str(today)
        business_date = request.GET.get("business_date") or str(today)
        sales = (
            Sale.objects.filter(business_date__gte=start_date, business_date__lte=end_date)
            .select_related("customer")
            .order_by("-business_date", "-created_at")
        )
        context = {
            "today": today,
            "start_date": start_date,
            "end_date": end_date,
            "business_date": business_date,
            "preset_week_start": today - timedelta(days=6),
            "preset_month_start": today.replace(day=1),
            "sales": sales,
        }
        return render(request, self.template_name, context)


class SaleCloseDayView(View):
    def post(self, request):
        business_date = request.POST.get("business_date") or str(timezone.localdate())
        try:
            created_sales = close_sales_for_business_date(business_date)
            if created_sales:
                messages.success(request, f"Cierre diario generado. Ventas creadas: {len(created_sales)}.")
            else:
                messages.info(request, "No hay pedidos entregados pendientes para esa fecha.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect(
            f"{reverse('core:sale_list')}?business_date={business_date}"
            f"&start_date={business_date}&end_date={business_date}"
        )

class PricingListView(View):
    template_name = "core/pricing_list.html"

    def get(self, request):
        overhead_raw = request.GET.get("overhead_fixed")
        if overhead_raw is None:
            overhead_raw = request.GET.get("overhead_pct", str(DEFAULT_OVERHEAD_FIXED))
        margin_raw = request.GET.get("margin_pct", str(DEFAULT_MARGIN_PCT))
        params = SimulationParams(overhead_fixed=overhead_raw, margin_pct=margin_raw)
        result = simulate_pricing(params)
        payload = build_simulator_payload(params)
        context = {
            "overhead_fixed": result["overhead_fixed"],
            "margin_pct": result["margin_pct"],
            "rows": result["rows"],
            "simulator_payload_json": json.dumps(payload),
        }
        return render(request, self.template_name, context)


class CustomerListView(ListView):
    model = Customer
    template_name = "core/customer_list.html"
    context_object_name = "customers"

    def get_queryset(self):
        return Customer.objects.order_by("first_name", "last_name")


class CustomerCreateView(View):
    template_name = "core/customer_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": CustomerForm()})

    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente creado.")
            return redirect("core:customer_list")
        return render(request, self.template_name, {"form": form})


class CustomerUpdateView(View):
    template_name = "core/customer_form.html"

    def get(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        return render(request, self.template_name, {"form": CustomerForm(instance=customer), "customer": customer})

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente actualizado.")
            return redirect("core:customer_list")
        return render(request, self.template_name, {"form": form, "customer": customer})


class CustomerDeleteView(View):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = False
        customer.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Cliente dado de baja.")
        return redirect("core:customer_list")


class OrderListView(ListView):
    model = Order
    template_name = "core/order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        return Order.objects.select_related("customer", "sale").prefetch_related("items__pizza").order_by(
            "-business_date", "-created_at"
        )


class OrderCreateView(View):
    template_name = "core/order_form.html"

    def get(self, request):
        form = OrderForm(initial={"business_date": timezone.localdate()})
        item_formset = self._build_formset()
        context = {
            "form": form,
            "item_formset": item_formset,
            "empty_item_form": item_formset.empty_form,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = OrderForm(request.POST)
        item_formset = self._build_formset(data=request.POST)
        if not form.is_valid() or not item_formset.is_valid():
            context = {
                "form": form,
                "item_formset": item_formset,
                "empty_item_form": item_formset.empty_form,
            }
            return render(request, self.template_name, context)
        if not self._has_items(item_formset):
            form.add_error(None, "Se requiere al menos un ítem de pedido.")
            context = {
                "form": form,
                "item_formset": item_formset,
                "empty_item_form": item_formset.empty_form,
            }
            return render(request, self.template_name, context)

        with transaction.atomic():
            if form.cleaned_data.get("is_new_customer"):
                customer = Customer.objects.create(
                    first_name=(form.cleaned_data.get("customer_first_name") or "").strip(),
                    last_name=(form.cleaned_data.get("customer_last_name") or "").strip(),
                    phone=(form.cleaned_data.get("customer_phone") or "").strip(),
                )
                form.instance.customer = customer
            form.instance.status = Order.Status.PENDING
            order = form.save()
            item_formset.instance = order
            item_formset.save()
        messages.success(request, "Pedido creado.")
        return redirect("core:order_list")

    def _build_formset(self, data=None):
        formset_cls = inlineformset_factory(
            Order,
            OrderItem,
            form=OrderItemForm,
            fields=["pizza", "quantity"],
            extra=1,
            can_delete=True,
        )
        return formset_cls(data=data, prefix="items")

    def _has_items(self, item_formset):
        for item_form in item_formset.forms:
            cleaned = getattr(item_form, "cleaned_data", None) or {}
            if cleaned and not cleaned.get("DELETE") and cleaned.get("pizza") and cleaned.get("quantity"):
                return True
        return False


class OrderUpdateView(View):
    template_name = "core/order_form.html"

    def get(self, request, pk):
        order = get_object_or_404(Order.objects.select_related("customer").prefetch_related("items__pizza"), pk=pk)
        if order.sale_id or order.status in {Order.Status.DELIVERED, Order.Status.CANCELLED}:
            messages.warning(request, "El pedido no puede editarse en su estado actual.")
            return redirect("core:order_list")
        form = OrderForm(instance=order)
        item_formset = self._build_formset(instance=order)
        context = {
            "form": form,
            "item_formset": item_formset,
            "empty_item_form": item_formset.empty_form,
            "order": order,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        order = get_object_or_404(Order.objects.select_related("customer").prefetch_related("items__pizza"), pk=pk)
        if order.sale_id or order.status in {Order.Status.DELIVERED, Order.Status.CANCELLED}:
            messages.warning(request, "El pedido no puede editarse en su estado actual.")
            return redirect("core:order_list")
        form = OrderForm(request.POST, instance=order)
        item_formset = self._build_formset(data=request.POST, instance=order)
        if not form.is_valid() or not item_formset.is_valid():
            context = {
                "form": form,
                "item_formset": item_formset,
                "empty_item_form": item_formset.empty_form,
                "order": order,
            }
            return render(request, self.template_name, context)
        if not self._has_items(item_formset):
            form.add_error(None, "Se requiere al menos un ítem de pedido.")
            context = {
                "form": form,
                "item_formset": item_formset,
                "empty_item_form": item_formset.empty_form,
                "order": order,
            }
            return render(request, self.template_name, context)

        with transaction.atomic():
            if form.cleaned_data.get("is_new_customer"):
                customer = Customer.objects.create(
                    first_name=(form.cleaned_data.get("customer_first_name") or "").strip(),
                    last_name=(form.cleaned_data.get("customer_last_name") or "").strip(),
                    phone=(form.cleaned_data.get("customer_phone") or "").strip(),
                )
                form.instance.customer = customer
            form.instance.status = order.status
            form.save()
            item_formset.save()
        messages.success(request, "Pedido actualizado.")
        return redirect("core:order_list")

    def _build_formset(self, data=None, instance=None):
        formset_cls = inlineformset_factory(
            Order,
            OrderItem,
            form=OrderItemForm,
            fields=["pizza", "quantity"],
            extra=0,
            can_delete=True,
        )
        return formset_cls(data=data, instance=instance, prefix="items")

    def _has_items(self, item_formset):
        for item_form in item_formset.forms:
            cleaned = getattr(item_form, "cleaned_data", None) or {}
            if cleaned and not cleaned.get("DELETE") and cleaned.get("pizza") and cleaned.get("quantity"):
                return True
        return False


class OrderChangeStatusView(View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        new_status = request.POST.get("new_status")
        try:
            change_order_status(order, new_status)
            messages.success(request, f"Pedido actualizado a {order.get_status_display()}.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("core:order_list")


class OrderDeleteView(View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if order.sale_id or order.status in {Order.Status.DELIVERED, Order.Status.CANCELLED}:
            messages.warning(request, "El pedido no puede eliminarse en su estado actual.")
            return redirect("core:order_list")
        order.delete()
        messages.success(request, "Pedido eliminado.")
        return redirect("core:order_list")


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
            {"form": IngredientForm(instance=ingredient), "ingredient": ingredient},
        )

    def post(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        form = IngredientForm(request.POST, instance=ingredient)
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
            pizza = form.save()
            messages.success(request, "Pizza creada. Ahora podés cargar la receta.")
            return redirect("core:pizza_update", pk=pizza.id)
        return render(request, self.template_name, {"form": form})


class PizzaUpdateView(View):
    template_name = "core/pizza_form.html"

    def get(self, request, pk):
        pizza = get_object_or_404(Pizza, pk=pk)
        recipe_items = pizza.recipe_items.select_related("ingredient").order_by("ingredient__name")
        return render(
            request,
            self.template_name,
            {"form": PizzaForm(instance=pizza), "pizza": pizza, "recipe_items": recipe_items},
        )

    def post(self, request, pk):
        pizza = get_object_or_404(Pizza, pk=pk)
        form = PizzaForm(request.POST, instance=pizza)
        recipe_items = pizza.recipe_items.select_related("ingredient").order_by("ingredient__name")
        if form.is_valid():
            form.save()
            messages.success(request, "Pizza actualizada.")
            return redirect("core:pizza_update", pk=pizza.id)
        return render(
            request,
            self.template_name,
            {"form": form, "pizza": pizza, "recipe_items": recipe_items},
        )


class PizzaDeleteView(View):
    def post(self, request, pk):
        pizza = get_object_or_404(Pizza, pk=pk)
        pizza.is_active = False
        pizza.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Pizza dada de baja.")
        return redirect("core:pizza_list")


class RecipeItemListView(View):
    def get(self, request):
        return redirect("core:pizza_list")


class RecipeItemCreateView(View):
    template_name = "core/recipe_form.html"

    def get(self, request, pizza_id):
        pizza = get_object_or_404(Pizza, pk=pizza_id)
        form = RecipeItemForm(fixed_pizza=pizza)
        return render(request, self.template_name, {"form": form, "pizza": pizza})

    def post(self, request, pizza_id):
        pizza = get_object_or_404(Pizza, pk=pizza_id)
        form = RecipeItemForm(request.POST, fixed_pizza=pizza)
        if form.is_valid():
            form.save()
            messages.success(request, "Insumo agregado a la receta.")
            return redirect("core:pizza_update", pk=pizza.id)
        return render(request, self.template_name, {"form": form, "pizza": pizza})


class RecipeItemUpdateView(View):
    template_name = "core/recipe_form.html"

    def get(self, request, pk):
        recipe = get_object_or_404(RecipeItem.objects.select_related("pizza", "ingredient"), pk=pk)
        form = RecipeItemForm(instance=recipe, fixed_pizza=recipe.pizza)
        return render(
            request,
            self.template_name,
            {"form": form, "recipe": recipe, "pizza": recipe.pizza},
        )

    def post(self, request, pk):
        recipe = get_object_or_404(RecipeItem.objects.select_related("pizza", "ingredient"), pk=pk)
        form = RecipeItemForm(request.POST, instance=recipe, fixed_pizza=recipe.pizza)
        if form.is_valid():
            form.save()
            messages.success(request, "Insumo de receta actualizado.")
            return redirect("core:pizza_update", pk=recipe.pizza_id)
        return render(
            request,
            self.template_name,
            {"form": form, "recipe": recipe, "pizza": recipe.pizza},
        )


class RecipeItemDeleteView(View):
    def post(self, request, pk):
        recipe = get_object_or_404(RecipeItem, pk=pk)
        pizza_id = recipe.pizza_id
        recipe.delete()
        messages.success(request, "Insumo eliminado de la receta.")
        return redirect("core:pizza_update", pk=pizza_id)
