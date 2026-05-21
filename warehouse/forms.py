from django import forms
from django.forms import inlineformset_factory

from core.forms import StyledFormMixin
from core.models import Store
from warehouse.models import (
    Product,
    Purchase,
    PurchaseLine,
    StockTransfer,
    StockTransferLine,
    Supplier,
    SupplierPayment,
)


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "sku",
            "name",
            "category",
            "department",
            "location",
            "list_price",
            "reorder_min",
            "stock_max",
        )
        labels = {
            "department": "Departamento",
            "location": "Localización en almacén",
            "reorder_min": "Mínimo de reorden",
            "stock_max": "Existencia máxima",
        }
        widgets = {
            "department": forms.TextInput(
                attrs={"placeholder": "Ej. Plomería, Herramientas, Pintura…"}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Ej. Pasillo A-3, Estante 12…"}
            ),
        }


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


class StockTransferForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ("from_store", "to_store", "notes")
        labels = {
            "from_store": "Tienda origen",
            "to_store": "Tienda destino",
            "notes": "Notas",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from core.store_access import stores_for_user

        qs = stores_for_user(user) if user else Store.objects.none()
        self.fields["from_store"].queryset = qs
        self.fields["to_store"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        origin = cleaned.get("from_store")
        dest = cleaned.get("to_store")
        if origin and dest and origin.pk == dest.pk:
            raise forms.ValidationError("Origen y destino deben ser tiendas distintas.")
        return cleaned


class StockTransferLineForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockTransferLine
        fields = ("product", "quantity")
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
        }


StockTransferLineFormSet = inlineformset_factory(
    StockTransfer,
    StockTransferLine,
    form=StockTransferLineForm,
    fields=("product", "quantity"),
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class StockImportForm(StyledFormMixin, forms.Form):
    MODE_SET = "set"
    MODE_ADD = "add"
    MODE_CHOICES = (
        (MODE_SET, "Fijar existencia"),
        (MODE_ADD, "Sumar al existente"),
    )

    file = forms.FileField(
        label="Archivo Excel (.xlsx)",
        widget=forms.FileInput(attrs={"accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    )
    mode = forms.ChoiceField(
        label="¿Qué hacer con la columna cantidad?",
        choices=MODE_CHOICES,
        initial=MODE_SET,
        widget=forms.RadioSelect,
    )
