from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from core.money import format_mxn
from core.views.base import BaseView
from core.views.permissions import (
    CanAddSaleMixin,
    CanChangeSaleMixin,
    CanRunEodMixin,
    CanViewSalesMixin,
)
from sales.forms import EodForm, SaleCheckoutForm, SaleForm, SaleLineFormSet
from sales.models import DayClose, Sale
from sales.sale_workflow import (
    confirm_sale_payment,
    sale_form_context,
    save_sale_draft,
)
from sales.services.eod import build_sales_summary, run_eod
from warehouse.services.stock import apply_sale


class SaleListView(CanViewSalesMixin, BaseView, ListView):
    model = Sale
    template_name = "sales/sale_list.html"
    context_object_name = "sales"
    page_type = "Ventas"
    paginate_by = None

    def get_queryset(self):
        return (
            self.filter_by_stores(Sale.objects.all())
            .select_related("store")
            .prefetch_related("lines")
            .order_by("-created_at")[:200]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["drafts"] = [
            s for s in context["sales"] if s.status == Sale.Status.DRAFT
        ]
        context["show_store_column"] = self.show_store_column()
        return context


class SaleDraftView(BaseView, View):
    """Create or edit a draft sale (notes + line formset)."""

    template_name = "sales/sale_form.html"
    page_type = "Venta"

    def get_sale(self):
        return None

    def get_page_title(self):
        return "Nueva venta"

    def get(self, request, *args, **kwargs):
        sale = self.get_sale()
        form = SaleForm(instance=sale)
        formset = SaleLineFormSet(instance=sale, prefix="lines")
        context = sale_form_context(form, formset, sale=sale)
        context["type"] = self.page_type
        context["title"] = self.get_page_title()
        return self.render(context)

    def post(self, request, *args, **kwargs):
        sale = self.get_sale()
        sale_obj, form, formset = save_sale_draft(request, self.get_store(), sale=sale)
        if sale_obj is None:
            context = sale_form_context(form, formset, sale=sale)
            context["type"] = self.page_type
            context["title"] = self.get_page_title()
            return self.render(context)

        action = request.POST.get("action", "draft")
        if action == "checkout":
            messages.info(request, f"Venta #{sale_obj.pk}: revise el total y cobre.")
            return redirect("sale_checkout", pk=sale_obj.pk)

        if sale:
            messages.success(request, "Cambios guardados.")
            return redirect("sale_edit", pk=sale_obj.pk)

        messages.success(request, f"Venta #{sale_obj.pk} guardada como pendiente.")
        return redirect("sale_edit", pk=sale_obj.pk)

    def render(self, context):
        from django.shortcuts import render

        return render(self.request, self.template_name, context)


class SaleCreateView(CanAddSaleMixin, SaleDraftView):
    page_title = "Nueva venta"


class SaleUpdateView(CanChangeSaleMixin, SaleDraftView):
    page_title = "Venta pendiente"

    def get_sale(self):
        return get_object_or_404(
            self.filter_by_stores(Sale.objects.filter(status=Sale.Status.DRAFT)),
            pk=self.kwargs["pk"],
        )

    def get_page_title(self):
        return f"Venta pendiente #{self.kwargs['pk']}"


class SaleCheckoutView(CanChangeSaleMixin, BaseView, UpdateView):
    model = Sale
    form_class = SaleCheckoutForm
    template_name = "sales/sale_checkout.html"
    page_type = "Cobrar venta"

    def get_queryset(self):
        return self.filter_by_stores(
            Sale.objects.filter(status=Sale.Status.DRAFT)
        ).prefetch_related("lines__product")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lines"] = list(self.object.lines.select_related("product"))
        context["total"] = self.object.total()
        context["store"] = self.get_store()
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("payment_method", Sale.PaymentMethod.CASH)
        return initial

    def form_valid(self, form):
        sale = self.object
        try:
            confirm_sale_payment(
                sale,
                form.cleaned_data["payment_method"],
                form.cleaned_data.get("amount_tendered"),
            )
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)

        apply_sale(sale, self.request.user)
        msg = f"Venta #{sale.pk} cobrada."
        if sale.change_amount is not None:
            msg += f" Cambio: {format_mxn(sale.change_amount)}."
        messages.success(self.request, msg)
        url = reverse("print_sale", kwargs={"pk": sale.pk})
        return redirect(f"{url}?auto=1")

    def form_invalid(self, form):
        messages.error(self.request, "Revise los datos de cobro.")
        return super().form_invalid(form)


class PrintSaleView(CanViewSalesMixin, BaseView, TemplateView):
    template_name = "sales/print_sale.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale = get_object_or_404(
            self.filter_by_stores(
                Sale.objects.filter(status=Sale.Status.CONFIRMED)
            )
            .select_related("user", "store")
            .prefetch_related("lines__product"),
            pk=self.kwargs["pk"],
        )
        context["store"] = sale.store
        context["sale"] = sale
        context["lines"] = sale.lines.select_related("product")
        context["printed_at"] = timezone.localtime()
        context["auto_print"] = self.request.GET.get("auto") in ("1", "true", "yes")
        return context


class EodView(CanRunEodMixin, BaseView, FormView):
    form_class = EodForm
    template_name = "sales/eod.html"
    success_url = reverse_lazy("eod")
    page_type = "Cierre día"

    def get_initial(self):
        return {"date": timezone.localdate()}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["closes"] = (
            self.filter_by_stores(DayClose.objects.all())
            .select_related("store")
            .order_by("-date")[:30]
        )
        context["write_store"] = self.get_write_store()
        form = context.get("form") or self.get_form()
        context["ticket_date"] = (
            form.initial.get("date") if hasattr(form, "initial") else None
        ) or timezone.localdate()
        return context

    def form_valid(self, form):
        close, created = run_eod(
            self.get_store(),
            form.cleaned_data["date"],
            self.request.user,
            notes=form.cleaned_data.get("notes") or "",
            force=form.cleaned_data.get("force") or False,
        )
        if created:
            messages.success(
                self.request, f"Cierre generado. PDF: {close.export_pdf_path}"
            )
        else:
            messages.warning(
                self.request,
                "Ya existía cierre para ese día. Use 'Regenerar' o borre el cierre en admin.",
            )
        return super().form_valid(form)


class PrintEodSalesView(CanRunEodMixin, BaseView, TemplateView):
    template_name = "sales/print_eod_sales.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_s = self.request.GET.get("date")
        try:
            business_date = date.fromisoformat(date_s) if date_s else timezone.localdate()
        except ValueError:
            business_date = timezone.localdate()
        store = self.get_store()
        context["store"] = store
        context["business_date"] = business_date
        context["summary"] = build_sales_summary(store, business_date)
        context["printed_at"] = timezone.localtime()
        context["auto_print"] = self.request.GET.get("auto") in ("1", "true", "yes")
        return context
