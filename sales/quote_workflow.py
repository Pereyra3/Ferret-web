"""Quote (presupuesto) draft helpers, mirroring the sale draft flow.

A quote never touches inventory, money or day-close totals; it is purely an
informational document for the customer.
"""

from django.contrib import messages

from sales.forms import QuoteForm, QuoteLineFormSet
from sales.models import Quote, Sale, SaleLine


def quote_line_count(formset) -> int:
    filled = 0
    for f in formset.forms:
        d = getattr(f, "cleaned_data", None) or {}
        if d.get("DELETE"):
            continue
        if d.get("product"):
            filled += 1
    return filled


def save_quote(request, store, *, quote=None):
    form = QuoteForm(request.POST, instance=quote)
    formset = QuoteLineFormSet(request.POST, instance=quote, prefix="lines")

    if not (form.is_valid() and formset.is_valid()):
        return None, form, formset

    if quote_line_count(formset) < 1:
        messages.error(request, "Agregue al menos una línea de producto (escaneo o manual).")
        return None, form, formset

    quote_obj = form.save(commit=False)
    quote_obj.store = store
    quote_obj.user = request.user
    quote_obj.save()
    formset.instance = quote_obj
    formset.save()
    return quote_obj, form, formset


def quote_form_context(form, formset, quote=None):
    return {
        "form": form,
        "formset": formset,
        "quote": quote,
        "is_edit": quote is not None,
    }


def quote_to_sale_draft(quote: Quote, user, store) -> Sale:
    """Copy quote lines into a new draft sale (no stock or payment yet)."""
    note_parts = []
    if quote.customer_name:
        note_parts.append(f"Cliente: {quote.customer_name}")
    if quote.notes:
        note_parts.append(quote.notes)
    note_parts.append(f"(desde presupuesto #{quote.pk})")

    sale = Sale.objects.create(
        store=store,
        user=user,
        status=Sale.Status.DRAFT,
        notes=" — ".join(note_parts),
    )
    SaleLine.objects.bulk_create(
        [
            SaleLine(
                sale=sale,
                product=line.product,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in quote.lines.select_related("product")
        ]
    )
    return sale
