from django import forms
from django.forms import inlineformset_factory

from .models import Product, Purchase, PurchaseLine, Sale, SaleLine, Supplier, SupplierPayment


def _widget_class(widget, base_class):
    existing = widget.attrs.get("class", "")
    if base_class not in existing.split():
        widget.attrs["class"] = (existing + " " + base_class).strip()


class StyledFormMixin:
    """Apply Bootstrap + ft-control classes to visible fields."""

    control_class = "form-control ft-control"
    select_class = "form-select ft-control"
    check_class = "form-check-input ft-check"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.HiddenInput):
                continue
            if isinstance(w, forms.CheckboxInput):
                _widget_class(w, self.check_class)
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                _widget_class(w, self.select_class)
            elif isinstance(w, forms.Textarea):
                _widget_class(w, self.control_class + " ft-textarea")
                w.attrs.setdefault("rows", 3)
            elif isinstance(
                w,
                (
                    forms.TextInput,
                    forms.NumberInput,
                    forms.EmailInput,
                    forms.URLInput,
                    forms.DateInput,
                    forms.DateTimeInput,
                    forms.TimeInput,
                ),
            ):
                _widget_class(w, self.control_class)


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ("sku", "name", "category", "list_price", "reorder_min")


class SaleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("payment_method", "notes")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Opcional: observaciones de la venta"}),
        }


class SaleLineEditForm(forms.ModelForm):
    class Meta:
        model = SaleLine
        fields = ("product", "quantity", "unit_price")
        widgets = {
            "product": forms.HiddenInput(),
            "quantity": forms.NumberInput(
                attrs={"step": "0.001", "min": "0.001", "class": "form-control form-control-sm js-line-qty ft-control"}
            ),
            "unit_price": forms.NumberInput(
                attrs={"step": "0.01", "min": "0", "class": "form-control form-control-sm js-line-price ft-control"}
            ),
        }


SaleLineFormSet = inlineformset_factory(
    Sale,
    SaleLine,
    form=SaleLineEditForm,
    fields=("product", "quantity", "unit_price"),
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class PurchaseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ("supplier", "reference")
        widgets = {
            "reference": forms.TextInput(attrs={"placeholder": "Factura, remisión, etc."}),
        }


class PurchaseLineForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseLine
        fields = ("product", "quantity", "unit_cost")
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
            "unit_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }


PurchaseLineFormSet = inlineformset_factory(
    Purchase,
    PurchaseLine,
    form=PurchaseLineForm,
    fields=("product", "quantity", "unit_cost"),
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class SupplierPaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ("supplier", "amount", "note", "reference")
        widgets = {
            "note": forms.Textarea(attrs={"rows": 2}),
            "reference": forms.TextInput(attrs={"placeholder": "Nº transferencia, cheque, etc."}),
        }


class StockAdjustForm(StyledFormMixin, forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label="Producto")
    quantity_delta = forms.DecimalField(
        label="Ajuste (+ entrada / − salida)",
        max_digits=14,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "placeholder": "Ej. 10 o -2.5"}),
    )
    note = forms.CharField(
        required=False,
        label="Motivo",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Merma, conteo, corrección…"}),
    )


class EodForm(StyledFormMixin, forms.Form):
    date = forms.DateField(label="Día a cerrar", widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Texto opcional en el PDF"}),
        label="Notas al PDF",
    )
    force = forms.BooleanField(required=False, label="Regenerar si ya existe cierre")
