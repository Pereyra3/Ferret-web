from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncYear
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import (
    EodForm,
    ProductForm,
    PurchaseForm,
    PurchaseLineFormSet,
    SaleForm,
    SaleLineFormSet,
    StockAdjustForm,
    SupplierPaymentForm,
)
from .models import DayClose, Product, Purchase, Sale, StockLevel, Supplier
from .services.eod import run_eod
from .services.stock import apply_adjustment, apply_purchase, apply_sale


def _store(request):
    store = getattr(request, "default_store", None)
    if callable(store):
        store = store()
    if store is None:
        raise ValueError("No hay tienda por defecto. Ejecute: python manage.py setup_defaults")
    return store


def _parse_range(request):
    today = timezone.localdate()
    default_from = today - timedelta(days=30)
    from_s = request.GET.get("from")
    to_s = request.GET.get("to")
    try:
        d_from = date.fromisoformat(from_s) if from_s else default_from
    except ValueError:
        d_from = default_from
    try:
        d_to = date.fromisoformat(to_s) if to_s else today
    except ValueError:
        d_to = today
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    return d_from, d_to


@login_required
def dashboard(request):
    d_from, d_to = _parse_range(request)
    return render(
        request,
        "store_ops/dashboard.html",
        {"range_from": d_from, "range_to": d_to},
    )


def _trunc_for_granularity(granularity: str):
    if granularity == "month":
        return TruncMonth("created_at")
    if granularity == "year":
        return TruncYear("created_at")
    return TruncDay("created_at")


@login_required
@require_GET
def api_sales_series(request):
    store = _store(request)
    d_from, d_to = _parse_range(request)
    granularity = request.GET.get("granularity", "day")
    start = timezone.make_aware(datetime.combine(d_from, time.min))
    end = timezone.make_aware(datetime.combine(d_to, time.max))

    line_total = ExpressionWrapper(
        F("quantity") * F("unit_price"),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    )
    trunc = _trunc_for_granularity(granularity)
    qs = (
        SaleLine.objects.filter(
            sale__store=store,
            sale__status=Sale.Status.CONFIRMED,
            sale__created_at__gte=start,
            sale__created_at__lte=end,
        )
        .annotate(bucket=trunc)
        .values("bucket")
        .annotate(total=Coalesce(Sum(line_total), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4))))
        .order_by("bucket")
    )
    labels = []
    values = []
    for row in qs:
        b = row["bucket"]
        if hasattr(b, "date"):
            labels.append(b.date().isoformat())
        elif hasattr(b, "isoformat"):
            labels.append(b.isoformat())
        else:
            labels.append(str(b))
        values.append(float(row["total"]))
    return JsonResponse({"labels": labels, "values": values, "granularity": granularity})


@login_required
@require_GET
def api_suppliers_balance(request):
    store = _store(request)
    data = []
    for s in Supplier.objects.all().order_by("name"):
        data.append(
            {
                "name": s.name,
                "balance": float(s.balance(store)),
                "purchases": float(s.purchases_total(store)),
                "payments": float(s.payments_total(store)),
            }
        )
    return JsonResponse({"suppliers": data})


@login_required
@require_GET
def api_products_movement(request):
    store = _store(request)
    d_from, d_to = _parse_range(request)
    start = timezone.make_aware(datetime.combine(d_from, time.min))
    end = timezone.make_aware(datetime.combine(d_to, time.max))
    line_qty = (
        SaleLine.objects.filter(
            sale__store=store,
            sale__status=Sale.Status.CONFIRMED,
            sale__created_at__gte=start,
            sale__created_at__lte=end,
        )
        .values("product_id", "product__sku", "product__name")
        .annotate(qty=Coalesce(Sum("quantity"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4))))
        .order_by("-qty")[:25]
    )
    items = [
        {
            "sku": r["product__sku"],
            "name": r["product__name"],
            "qty": float(r["qty"]),
        }
        for r in line_qty
    ]
    return JsonResponse({"products": items})


@login_required
def product_list(request):
    products = Product.objects.all().order_by("name")
    store = _store(request)
    low = []
    for p in products:
        q = p.stock_quantity(store)
        if p.reorder_min and q <= p.reorder_min:
            low.append((p, q))
    return render(request, "store_ops/product_list.html", {"products": products, "low_stock": low})


@login_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto creado.")
            return redirect("product_list")
    else:
        form = ProductForm()
    return render(request, "store_ops/product_form.html", {"form": form, "title": "Nuevo producto"})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado.")
            return redirect("product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "store_ops/product_form.html", {"form": form, "title": "Editar producto"})


@login_required
def sale_list(request):
    store = _store(request)
    sales = Sale.objects.filter(store=store).order_by("-created_at")[:200]
    return render(request, "store_ops/sale_list.html", {"sales": sales})


@login_required
def sale_create(request):
    store = _store(request)
    if request.method == "POST":
        form = SaleForm(request.POST)
        formset = SaleLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            sale = form.save(commit=False)
            sale.store = store
            sale.user = request.user
            sale.status = Sale.Status.CONFIRMED
            sale.save()
            formset.instance = sale
            formset.save()
            apply_sale(sale, request.user)
            messages.success(request, "Venta registrada e inventario actualizado.")
            return redirect("sale_list")
    else:
        form = SaleForm()
        formset = SaleLineFormSet()
    return render(request, "store_ops/sale_form.html", {"form": form, "formset": formset})


@login_required
def purchase_create(request):
    store = _store(request)
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        formset = PurchaseLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            purchase = form.save(commit=False)
            purchase.store = store
            purchase.user = request.user
            purchase.save()
            formset.instance = purchase
            formset.save()
            apply_purchase(purchase, request.user)
            messages.success(request, "Compra registrada e inventario actualizado.")
            return redirect("dashboard")
    else:
        form = PurchaseForm()
        formset = PurchaseLineFormSet()
    return render(request, "store_ops/purchase_form.html", {"form": form, "formset": formset})


@login_required
def payment_create(request):
    store = _store(request)
    if request.method == "POST":
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            pay = form.save(commit=False)
            pay.store = store
            pay.user = request.user
            pay.save()
            messages.success(request, "Pago a proveedor registrado.")
            return redirect("dashboard")
    else:
        form = SupplierPaymentForm()
    return render(request, "store_ops/payment_form.html", {"form": form})


@login_required
def stock_adjust(request):
    store = _store(request)
    if request.method == "POST":
        form = StockAdjustForm(request.POST)
        if form.is_valid():
            apply_adjustment(
                store,
                form.cleaned_data["product"],
                form.cleaned_data["quantity_delta"],
                request.user,
            )
            messages.success(request, "Ajuste de inventario aplicado.")
            return redirect("product_list")
    else:
        form = StockAdjustForm()
    return render(request, "store_ops/stock_adjust.html", {"form": form})


@login_required
def eod_view(request):
    store = _store(request)
    if request.method == "POST":
        form = EodForm(request.POST)
        if form.is_valid():
            close, created = run_eod(
                store,
                form.cleaned_data["date"],
                request.user,
                notes=form.cleaned_data.get("notes") or "",
                force=form.cleaned_data.get("force") or False,
            )
            if created:
                messages.success(request, f"Cierre generado. PDF: {close.export_pdf_path}")
            else:
                messages.warning(request, "Ya existía cierre para ese día. Use 'Regenerar' o borre el cierre en admin.")
            return redirect("eod")
    else:
        form = EodForm(initial={"date": timezone.localdate()})
    closes = DayClose.objects.filter(store=store).order_by("-date")[:30]
    return render(request, "store_ops/eod.html", {"form": form, "closes": closes})


@login_required
def stock_list(request):
    store = _store(request)
    rows = (
        StockLevel.objects.filter(store=store)
        .select_related("product")
        .order_by("product__name")
    )
    return render(request, "store_ops/stock_list.html", {"rows": rows})
