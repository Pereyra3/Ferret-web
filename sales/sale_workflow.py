"""Sale draft/checkout helpers (shared by CBVs and tests)."""

from decimal import Decimal

from django.contrib import messages

from core.money import format_mxn
from sales.forms import SaleForm, SaleLineFormSet
from sales.models import Sale


def sale_line_count(formset) -> int:
    filled = 0
    for f in formset.forms:
        d = getattr(f, "cleaned_data", None) or {}
        if d.get("DELETE"):
            continue
        if d.get("product"):
            filled += 1
    return filled


def total_from_formset(formset) -> Decimal:
    total = Decimal(0)
    for f in formset.forms:
        d = getattr(f, "cleaned_data", None) or {}
        if d.get("DELETE") or not d.get("product"):
            continue
        total += Decimal(d["quantity"]) * Decimal(d["unit_price"])
    return total


def resolve_cash_payment(total: Decimal, payment_method: str, amount_tendered) -> tuple:
    if payment_method != Sale.PaymentMethod.CASH:
        return None, None
    if amount_tendered is None:
        raise ValueError("Indique el efectivo recibido para calcular el cambio.")
    tendered = Decimal(amount_tendered)
    if tendered < total:
        raise ValueError(
            f"Efectivo insuficiente: recibido {format_mxn(tendered)} — total {format_mxn(total)}."
        )
    return tendered, tendered - total


def save_sale_draft(request, store, *, sale=None):
    form = SaleForm(request.POST, instance=sale)
    formset = SaleLineFormSet(request.POST, instance=sale, prefix="lines")

    if not (form.is_valid() and formset.is_valid()):
        return None, form, formset

    if sale_line_count(formset) < 1:
        messages.error(request, "Agregue al menos una línea de producto (escaneo o manual).")
        return None, form, formset

    sale_obj = form.save(commit=False)
    sale_obj.store = store
    sale_obj.user = request.user
    sale_obj.status = Sale.Status.DRAFT
    sale_obj.amount_tendered = None
    sale_obj.change_amount = None
    sale_obj.save()
    formset.instance = sale_obj
    formset.save()
    return sale_obj, form, formset


def confirm_sale_payment(sale, payment_method: str, amount_tendered_raw) -> None:
    total = sale.total()
    tendered, change = resolve_cash_payment(total, payment_method, amount_tendered_raw)
    sale.payment_method = payment_method
    sale.amount_tendered = tendered
    sale.change_amount = change
    sale.status = Sale.Status.CONFIRMED
    sale.save(update_fields=["payment_method", "amount_tendered", "change_amount", "status"])


def sale_form_context(form, formset, sale=None):
    return {
        "form": form,
        "formset": formset,
        "sale": sale,
        "is_edit": sale is not None,
    }
