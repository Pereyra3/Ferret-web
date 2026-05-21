from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView
from openpyxl import Workbook

from core.views.base import BaseView
from core.views.permissions import (
    CanAddProductMixin,
    CanAddPurchaseMixin,
    CanAddStockTransferMixin,
    CanAddSupplierPaymentMixin,
    CanChangeProductMixin,
    CanChangeStockMixin,
    CanChangeStockTransferMixin,
    CanViewProductsMixin,
    CanViewStockMixin,
    CanViewStockTransferMixin,
)
from warehouse.inventory import (
    inventory_filter_options,
    inventory_filter_query,
    inventory_filters,
    stock_rows,
)
from warehouse.forms import (
    ProductForm,
    PurchaseForm,
    PurchaseLineFormSet,
    StockAdjustForm,
    StockImportForm,
    StockTransferForm,
    StockTransferLineFormSet,
    SupplierPaymentForm,
)
from warehouse.models import Product, Purchase, StockTransfer, SupplierPayment
from warehouse.services.stock import (
    accept_transfer,
    apply_adjustment,
    apply_purchase,
    reject_transfer,
    user_can_accept_transfer,
)
from warehouse.services.stock_import import (
    StockImportError,
    apply_stock_import,
    parse_stock_rows,
)


class ProductListView(CanViewProductsMixin, BaseView, ListView):
    model = Product
    template_name = "warehouse/product_list.html"
    context_object_name = "products"
    page_type = "Productos"

    def get_queryset(self):
        return Product.objects.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_ids = self.get_store_ids()
        low = []
        from warehouse.inventory import aggregate_stock_quantity

        for product in context["products"]:
            if len(store_ids) == 1:
                from core.models import Store

                qty = product.stock_quantity(Store.objects.get(pk=store_ids[0]))
            else:
                qty = aggregate_stock_quantity(product, store_ids)
            if product.reorder_min and qty <= product.reorder_min:
                low.append((product, qty))
        context["low_stock"] = low
        return context


class ProductCreateView(CanAddProductMixin, BaseView, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "warehouse/product_form.html"
    success_url = reverse_lazy("product_list")
    page_type = "Productos"
    page_title = "Nuevo producto"

    def form_valid(self, form):
        messages.success(self.request, "Producto creado.")
        return super().form_valid(form)


class ProductUpdateView(CanChangeProductMixin, BaseView, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "warehouse/product_form.html"
    success_url = reverse_lazy("product_list")
    page_type = "Productos"
    page_title = "Editar producto"

    def form_valid(self, form):
        messages.success(self.request, "Producto actualizado.")
        return super().form_valid(form)


class PurchaseCreateView(BaseView, CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "warehouse/purchase_form.html"
    success_url = reverse_lazy("dashboard")
    page_type = "Compra proveedor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "formset" not in context:
            context["formset"] = PurchaseLineFormSet(prefix="lines")
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = PurchaseLineFormSet(request.POST, prefix="lines")
        if form.is_valid() and formset.is_valid():
            return self._save_purchase(form, formset)
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )

    def _save_purchase(self, form, formset):
        store = self.get_store()
        purchase = form.save(commit=False)
        purchase.store = store
        purchase.user = self.request.user
        purchase.save()
        formset.instance = purchase
        formset.save()
        apply_purchase(purchase, self.request.user)
        messages.success(self.request, "Compra registrada e inventario actualizado.")
        return redirect(self.success_url)


class PaymentCreateView(CanAddSupplierPaymentMixin, BaseView, CreateView):
    model = SupplierPayment
    form_class = SupplierPaymentForm
    template_name = "warehouse/payment_form.html"
    success_url = reverse_lazy("dashboard")
    page_type = "Pago proveedor"

    def form_valid(self, form):
        pay = form.save(commit=False)
        pay.store = self.get_store()
        pay.user = self.request.user
        pay.save()
        messages.success(self.request, "Pago a proveedor registrado.")
        return super().form_valid(form)


class StockAdjustView(CanChangeStockMixin, BaseView, FormView):
    form_class = StockAdjustForm
    template_name = "warehouse/stock_adjust.html"
    success_url = reverse_lazy("product_list")
    page_type = "Ajuste inventario"

    def form_valid(self, form):
        apply_adjustment(
            self.get_store(),
            form.cleaned_data["product"],
            form.cleaned_data["quantity_delta"],
            self.request.user,
        )
        messages.success(self.request, "Ajuste de inventario aplicado.")
        return super().form_valid(form)


class StockListView(CanViewStockMixin, BaseView, TemplateView):
    template_name = "warehouse/stock_list.html"
    page_type = "Inventario"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_ids = self.get_store_ids()
        low_only = self.request.GET.get("low") in ("1", "true", "yes")
        suggested_only = self.request.GET.get("suggested") in ("1", "true", "yes")
        if suggested_only:
            low_only = False
        department, location = inventory_filters(self.request)
        rows = stock_rows(
            store_ids,
            low_only=low_only,
            suggested_only=suggested_only,
            department=department,
            location=location,
        )
        context["store_scope_label"] = self.get_store_selection_label()
        context["rows"] = rows
        context["low_only"] = low_only
        context["suggested_only"] = suggested_only
        context["suggested_total"] = (
            sum((r["suggested"] for r in rows), Decimal(0)) if suggested_only else None
        )
        departments, locations = inventory_filter_options()
        context["department_filter"] = department
        context["location_filter"] = location
        context["departments"] = departments
        context["locations"] = locations
        context["filter_query"] = inventory_filter_query(department, location)
        return context


class PrintStockSuggestedView(CanViewStockMixin, BaseView, TemplateView):
    template_name = "warehouse/print_stock_suggested.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_ids = self.get_store_ids()
        department, location = inventory_filters(self.request)
        rows = stock_rows(
            store_ids,
            suggested_only=True,
            department=department,
            location=location,
        )
        context["store"] = self.get_write_store()
        context["store_scope_label"] = self.get_store_selection_label()
        context["rows"] = rows
        context["suggested_total"] = sum((r["suggested"] for r in rows), Decimal(0))
        context["printed_at"] = timezone.localtime()
        context["auto_print"] = self.request.GET.get("auto") in ("1", "true", "yes")
        return context


class StockTransferListView(CanViewStockTransferMixin, BaseView, TemplateView):
    template_name = "warehouse/stock_transfer_list.html"
    page_type = "Transferencias"

    def get_context_data(self, **kwargs):
        from core.store_access import stores_for_user

        context = super().get_context_data(**kwargs)
        store_ids = list(stores_for_user(self.request.user).values_list("pk", flat=True))
        base = StockTransfer.objects.select_related(
            "from_store", "to_store", "user"
        ).prefetch_related("lines__product")
        pending = StockTransfer.Status.PENDING
        incoming = list(
            base.filter(to_store_id__in=store_ids, status=pending)
        )
        for transfer in incoming:
            transfer.may_review = user_can_accept_transfer(
                self.request.user, transfer
            )
        context["incoming_pending"] = incoming
        context["outgoing_pending"] = base.filter(
            from_store_id__in=store_ids, status=pending
        )
        return context


class StockTransferAcceptView(CanChangeStockTransferMixin, BaseView, View):
    http_method_names = ["post"]

    def post(self, request, pk, *args, **kwargs):
        transfer = get_object_or_404(StockTransfer, pk=pk)
        if not user_can_accept_transfer(request.user, transfer):
            messages.error(
                request,
                "No puede aceptar transferencias para esta tienda destino.",
            )
            return redirect("stock_transfer_list")
        try:
            accept_transfer(transfer, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("stock_transfer_list")
        messages.success(
            request,
            f"Transferencia #{transfer.pk} aceptada. Stock actualizado.",
        )
        return redirect("stock_transfer_list")


class StockTransferRejectView(CanChangeStockTransferMixin, BaseView, View):
    http_method_names = ["post"]

    def post(self, request, pk, *args, **kwargs):
        transfer = get_object_or_404(StockTransfer, pk=pk)
        if not user_can_accept_transfer(request.user, transfer):
            messages.error(
                request,
                "No puede rechazar transferencias para esta tienda destino.",
            )
            return redirect("stock_transfer_list")
        try:
            reject_transfer(transfer, request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("stock_transfer_list")
        messages.success(request, f"Transferencia #{transfer.pk} rechazada.")
        return redirect("stock_transfer_list")


class StockTransferCreateView(CanAddStockTransferMixin, BaseView, CreateView):
    model = StockTransfer
    form_class = StockTransferForm
    template_name = "warehouse/stock_transfer_form.html"
    success_url = reverse_lazy("stock_transfer_list")
    page_type = "Transferencia"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["formset"] = kwargs.get("formset") or StockTransferLineFormSet()
        return context

    @transaction.atomic
    def _save_transfer(self, form, formset):
        transfer = form.save(commit=False)
        transfer.user = self.request.user
        transfer.status = StockTransfer.Status.PENDING
        transfer.save()
        formset.instance = transfer
        formset.save()
        messages.success(
            self.request,
            f"Solicitud #{transfer.pk} enviada a {transfer.to_store.name}. "
            "Un encargado de esa tienda debe aceptarla.",
        )
        return redirect(self.success_url)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = StockTransferLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            return self._save_transfer(form, formset)
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )


class StockImportView(CanChangeStockMixin, BaseView, FormView):
    form_class = StockImportForm
    template_name = "warehouse/stock_import.html"
    success_url = reverse_lazy("stock_list")
    page_type = "Importar inventario"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["write_store"] = self.get_write_store()
        return context

    def form_valid(self, form):
        store = self.get_write_store()
        uploaded = form.cleaned_data["file"]
        try:
            rows, sku_col, qty_col = parse_stock_rows(uploaded)
            applied = apply_stock_import(
                store,
                self.request.user,
                rows,
                mode=form.cleaned_data["mode"],
            )
        except StockImportError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Inventario actualizado en {store.name}: {applied} producto(s) "
            f"(columnas {sku_col} / {qty_col}).",
        )
        return super().form_valid(form)


class StockImportSampleView(CanChangeStockMixin, BaseView, View):
    """Download a minimal .xlsx template for stock import."""

    def get(self, request, *args, **kwargs):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Inventario"
        sheet.append(["sku", "cantidad"])
        sheet.append(["SKU-EJEMPLO", 100])
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="plantilla_inventario.xlsx"'
        workbook.save(response)
        return response
