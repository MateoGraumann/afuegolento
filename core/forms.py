from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError

from core.models import Customer, Ingredient, Order, OrderItem, Pizza, RecipeItem


def _apply_styles(form):
    for field in form.fields.values():
        widget = field.widget
        existing = widget.attrs.get("class", "")
        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            css = "form-select"
        elif isinstance(widget, forms.CheckboxInput):
            css = "form-check-input"
        else:
            css = "form-control"
        widget.attrs["class"] = f"{existing} {css}".strip()


def _parse_decimal_input(raw_value):
    value = str(raw_value).strip()
    if not value:
        raise ValidationError("Este campo es obligatorio.")

    value = value.replace(" ", "")
    if "," in value and "." not in value:
        # Formato local: 50,000 -> 50.000
        normalized = value.replace(",", ".")
    elif "," in value and "." in value:
        # Si existen ambos separadores, usa el ultimo como decimal
        last_comma = value.rfind(",")
        last_dot = value.rfind(".")
        if last_comma > last_dot:
            normalized = value.replace(".", "").replace(",", ".")
        else:
            normalized = value.replace(",", "")
    else:
        normalized = value

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        raise ValidationError("Ingresá un número decimal válido.")


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "unit", "quantity", "total_price", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["name"].label = "Nombre"
        self.fields["unit"].label = "Unidad"
        self.fields["quantity"].label = "Cantidad"
        self.fields["total_price"].label = "Precio total"
        self.fields["is_active"].label = "Activo"


class PizzaForm(forms.ModelForm):
    class Meta:
        model = Pizza
        fields = ["name", "sale_price", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["name"].label = "Nombre"
        self.fields["sale_price"].label = "Precio de venta"
        self.fields["is_active"].label = "Activa"


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["first_name", "last_name", "phone", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["first_name"].label = "Nombre"
        self.fields["last_name"].label = "Apellido"
        self.fields["phone"].label = "Teléfono"
        self.fields["is_active"].label = "Activo"


class OrderForm(forms.ModelForm):
    is_new_customer = forms.BooleanField(required=False)
    customer_first_name = forms.CharField(required=False, max_length=120)
    customer_last_name = forms.CharField(required=False, max_length=120)
    customer_phone = forms.CharField(required=False, max_length=40)

    class Meta:
        model = Order
        fields = ["business_date", "customer", "total_envio", "direccion_envio", "notes"]
        widgets = {
            "business_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["business_date"].label = "Fecha operativa"
        self.fields["customer"].label = "Cliente"
        self.fields["is_new_customer"].label = "No existe cliente, cargar uno nuevo"
        self.fields["customer_first_name"].label = "Nombre del cliente"
        self.fields["customer_last_name"].label = "Apellido del cliente"
        self.fields["customer_phone"].label = "Teléfono del cliente"
        self.fields["total_envio"].label = "Total envío"
        self.fields["direccion_envio"].label = "Dirección envío"
        self.fields["notes"].label = "Notas"
        self.fields["customer"].queryset = Customer._default_manager.filter(is_active=True).order_by(
            "first_name", "last_name"
        )
        self.fields["customer"].required = False

    def clean(self):
        cleaned_data = super().clean()
        is_new_customer = cleaned_data.get("is_new_customer")
        customer = cleaned_data.get("customer")

        if is_new_customer:
            first_name = (cleaned_data.get("customer_first_name") or "").strip()
            last_name = (cleaned_data.get("customer_last_name") or "").strip()
            phone = (cleaned_data.get("customer_phone") or "").strip()
            if not first_name:
                self.add_error("customer_first_name", "Este campo es obligatorio.")
            if not last_name:
                self.add_error("customer_last_name", "Este campo es obligatorio.")
            if not phone:
                self.add_error("customer_phone", "Este campo es obligatorio.")
            cleaned_data["customer"] = None
        elif not customer:
            self.add_error("customer", "Seleccioná un cliente.")

        return cleaned_data


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ["pizza", "quantity"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["pizza"].label = "Pizza"
        self.fields["quantity"].label = "Cantidad"
        self.fields["pizza"].queryset = Pizza._default_manager.filter(is_active=True).order_by("name")


class RecipeItemForm(forms.ModelForm):
    quantity = forms.CharField()

    class Meta:
        model = RecipeItem
        fields = ["pizza", "ingredient", "quantity"]

    def __init__(self, *args, **kwargs):
        self.fixed_pizza = kwargs.pop("fixed_pizza", None)
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["ingredient"].queryset = Ingredient._default_manager.filter(is_active=True).order_by("name")
        self.fields["ingredient"].label = "Insumo"
        self.fields["quantity"].label = "Cantidad por pizza"

        if self.fixed_pizza is not None:
            self.fields.pop("pizza", None)
        else:
            self.fields["pizza"].queryset = Pizza._default_manager.filter(is_active=True).order_by("name")
            self.fields["pizza"].label = "Pizza"

    def clean_quantity(self):
        raw_value = self.data.get("quantity", "")
        parsed = _parse_decimal_input(raw_value)
        if parsed <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")
        return parsed.quantize(Decimal("0.001"))

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.fixed_pizza is not None:
            instance.pizza = self.fixed_pizza
        if commit:
            instance.save()
        return instance
