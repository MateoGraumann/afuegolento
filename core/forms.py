from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError

from core.models import Ingredient, IngredientMovement, Pizza, RecipeItem


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
        fields = ["name", "unit", "unit_price", "current_stock", "min_stock", "is_active"]

    def __init__(self, *args, **kwargs):
        allow_stock_edit = kwargs.pop("allow_stock_edit", True)
        super().__init__(*args, **kwargs)
        if not allow_stock_edit:
            self.fields.pop("current_stock", None)
        _apply_styles(self)
        self.fields["name"].label = "Nombre"
        self.fields["unit"].label = "Unidad"
        self.fields["unit_price"].label = "Precio unitario"
        if "current_stock" in self.fields:
            self.fields["current_stock"].label = "Stock actual"
        self.fields["min_stock"].label = "Stock mínimo"
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


class SaleEntryForm(forms.Form):
    business_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    pizza = forms.ModelChoiceField(queryset=Pizza._default_manager.filter(is_active=True))
    quantity = forms.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["business_date"].label = "Fecha operativa"
        self.fields["notes"].label = "Notas"
        self.fields["pizza"].label = "Pizza"
        self.fields["quantity"].label = "Cantidad"


class IngredientAdjustStockForm(forms.Form):
    direction = forms.ChoiceField(choices=IngredientMovement.Direction.choices)
    quantity = forms.DecimalField(min_value=Decimal("0.001"), max_digits=12, decimal_places=3)
    reference = forms.CharField(max_length=120)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["direction"].label = "Dirección"
        self.fields["quantity"].label = "Cantidad"
        self.fields["reference"].label = "Referencia"

    def clean_reference(self):
        value = self.cleaned_data["reference"]
        if not value.strip():
            raise ValidationError("La referencia es obligatoria.")
        return value


class RecipeItemForm(forms.ModelForm):
    quantity = forms.CharField()

    class Meta:
        model = RecipeItem
        fields = ["pizza", "ingredient", "quantity"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        self.fields["pizza"].queryset = Pizza._default_manager.filter(is_active=True).order_by("name")
        self.fields["ingredient"].queryset = Ingredient._default_manager.filter(is_active=True).order_by("name")
        self.fields["pizza"].label = "Pizza"
        self.fields["ingredient"].label = "Insumo"
        self.fields["quantity"].label = "Cantidad por pizza"

    def clean_quantity(self):
        raw_value = self.data.get("quantity", "")
        parsed = _parse_decimal_input(raw_value)
        if parsed <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")
        return parsed.quantize(Decimal("0.001"))
