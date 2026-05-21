from django import forms
from django.forms import inlineformset_factory

from core.forms import StyledFormMixin
from sales.models import Sale, SaleLine


class SaleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("notes",)
        widgets = {
            "notes": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Ej. pedido almacén, cliente, referencia…"}
            ),
        }


class SaleCheckoutForm(StyledFormMixin, forms.ModelForm):
    amount_tendered = forms.DecimalField(
        required=False,
        label="Efectivo recibido",
        max_digits=14,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "min": "0",
                "class": "form-control form-control-lg ft-control js-amount-tendered",
                "placeholder": "0.00",
            }
        ),
    )

    class Meta:
        model = Sale
        fields = ("payment_method",)
        widgets = {
            "payment_method": forms.Select(
                attrs={"class": "form-select form-select-lg ft-control js-payment-method"}
            ),
        }
        labels = {"payment_method": "Forma de pago"}


class SaleLineEditForm(forms.ModelForm):
    class Meta:
        model = SaleLine
        fields = ("product", "quantity", "unit_price")
        widgets = {
            "product": forms.HiddenInput(),
            "quantity": forms.NumberInput(
                attrs={
                    "step": "0.001",
                    "min": "0.001",
                    "class": "form-control form-control-sm js-line-qty ft-control",
                }
            ),
            "unit_price": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "form-control form-control-sm js-line-price ft-control",
                }
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


class EodForm(StyledFormMixin, forms.Form):
    date = forms.DateField(label="Día a cerrar", widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Texto opcional en el PDF"}),
        label="Notas al PDF",
    )
    force = forms.BooleanField(required=False, label="Regenerar si ya existe cierre")
