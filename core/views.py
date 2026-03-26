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
    IngredientAdjustStockForm,
    IngredientForm,
    OrderForm,
    OrderItemForm,
    PizzaForm,
    RecipeItemForm,
)
from core.models import Customer, Ingredient, IngredientMovement, Order, OrderItem, Pizza, RecipeItem, Sale
from core.services.metrics import (
    get_ingredient_consumption,
    get_low_and_negative_stock,
    get_profit_summary,
    get_top_pizzas_by_quantity,
    get_top_pizzas_by_revenue,
    get_unit_margin_by_pizza,
)
from core.services.sales import close_sales_for_business_date


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
            "recent_sales": Sale.objects.select_related("customer").order_by("-business_date", "-created_at")[:5],
        }
        return render(request, self.template_name, context)


class SaleListView(ListView):
    model = Sale
    template_name = "core/sale_list.html"
    context_object_name = "sales"

    def get_queryset(self):
        selected_date = self.request.GET.get("business_date") or str(timezone.localdate())
        return Sale.objects.filter(business_date=selected_date).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business_date"] = self.request.GET.get("business_date") or str(timezone.localdate())
        return context


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
            messages.error(request, exc.message)
        return redirect(f"{reverse('core:sale_list')}?business_date={business_date}")


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
        return Order.objects.select_related("customer").prefetch_related("items__pizza").order_by(
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
        if order.sale_id:
            messages.warning(request, "El pedido ya fue cerrado y no puede editarse.")
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
        if order.sale_id:
            messages.warning(request, "El pedido ya fue cerrado y no puede editarse.")
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


class OrderDeleteView(View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if order.sale_id:
            messages.warning(request, "El pedido ya fue cerrado y no puede eliminarse.")
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
