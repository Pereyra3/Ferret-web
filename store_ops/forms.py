from django import forms
from django.forms import inlineformset_factory

from .models import Product, Purchase, PurchaseLine, Sale, SaleLine, Supplier, SupplierPayment


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("sku", "name", "category", "reorder_min")


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("payment_method", "notes")


SaleLineFormSet = inlineformset_factory(
    Sale,
    SaleLine,
    fields=("product", "quantity", "unit_price"),
    extra=2,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ("supplier", "reference")


PurchaseLineFormSet = inlineformset_factory(
    Purchase,
    PurchaseLine,
    fields=("product", "quantity", "unit_cost"),
    extra=2,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ("supplier", "amount", "note", "reference")


class StockAdjustForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label="Producto")
    quantity_delta = forms.DecimalField(
        label="Ajuste (+ entrada / − salida)",
        max_digits=14,
        decimal_places=3,
    )
    note = forms.CharField(required=False, label="Motivo", max_length=200)


class EodForm(forms.Form):
    date = forms.DateField(label="Día a cerrar")
    notes = forms.CharField(required=False, widget=forms.Textarea, label="Notas al PDF")
    force = forms.BooleanField(required=False, label="Regenerar si ya existe cierre")
