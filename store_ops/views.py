from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncYear
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.functional import SimpleLazyObject, empty
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
from .models import (
    DayClose,
    Product,
    Purchase,
    PurchaseLine,
    Sale,
    SaleLine,
    StockLevel,
    SupplierPayment,
)
from .services.eod import run_eod
from .services.stock import apply_adjustment, apply_purchase, apply_sale


def _store(request):
    """Resolve default store (middleware attaches a SimpleLazyObject)."""
    store = getattr(request, "default_store", None)
    if store is None:
        raise ValueError("No default store. Sign in or run: python manage.py setup_defaults")
    if isinstance(store, SimpleLazyObject):
        if store._wrapped is empty:
            store._setup()
        store = store._wrapped
    if store is None:
        raise ValueError(
            "No store in database (DEFAULT_STORE_CODE or is_default). "
            "Run: python manage.py setup_defaults"
        )
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


def _range_bounds(d_from, d_to):
    start = timezone.make_aware(datetime.combine(d_from, time.min))
    end = timezone.make_aware(datetime.combine(d_to, time.max))
    return start, end


def _line_total_expr():
    return ExpressionWrapper(
        F("quantity") * F("unit_price"),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    )


def _cost_line_expr():
    return ExpressionWrapper(
        F("quantity") * F("unit_cost"),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    )


def _zero_decimal():
    return Value(0, output_field=DecimalField(max_digits=20, decimal_places=4))


def _bucket_totals(qs, trunc_field: str, sum_expr, granularity: str):
    trunc = _trunc_for_granularity(granularity, trunc_field)
    rows = (
        qs.annotate(bucket=trunc)
        .values("bucket")
        .annotate(total=Coalesce(Sum(sum_expr), _zero_decimal()))
        .order_by("bucket")
    )
    out = {}
    for row in rows:
        label = _format_bucket_label(row["bucket"], granularity)
        out[label] = float(row["total"] or 0)
    return out


def _profit_totals(store, start, end):
    line_total = _line_total_expr()
    cost_expr = _cost_line_expr()

    sales_total = Decimal(
        _confirmed_sale_lines(store, start, end).aggregate(
            t=Coalesce(Sum(line_total), _zero_decimal())
        )["t"]
        or 0
    )
    payments_total = Decimal(
        SupplierPayment.objects.filter(
            store=store,
            created_at__gte=start,
            created_at__lte=end,
        ).aggregate(t=Coalesce(Sum("amount"), _zero_decimal()))["t"]
        or 0
    )
    purchases_total = Decimal(
        PurchaseLine.objects.filter(
            purchase__store=store,
            purchase__created_at__gte=start,
            purchase__created_at__lte=end,
        ).aggregate(t=Coalesce(Sum(cost_expr), _zero_decimal()))["t"]
        or 0
    )

    net_cash = sales_total - payments_total
    net_operating = sales_total - purchases_total
    margin_cash = (net_cash / sales_total * 100) if sales_total else Decimal(0)
    margin_operating = (net_operating / sales_total * 100) if sales_total else Decimal(0)

    return {
        "sales_total": sales_total,
        "payments_total": payments_total,
        "purchases_total": purchases_total,
        "net_cash": net_cash,
        "net_operating": net_operating,
        "margin_cash": margin_cash,
        "margin_operating": margin_operating,
    }


def _profit_series(store, start, end, granularity: str):
    line_total = _line_total_expr()
    cost_expr = _cost_line_expr()

    sales_map = _bucket_totals(
        _confirmed_sale_lines(store, start, end),
        "sale__created_at",
        line_total,
        granularity,
    )
    payments_map = _bucket_totals(
        SupplierPayment.objects.filter(store=store, created_at__gte=start, created_at__lte=end),
        "created_at",
        F("amount"),
        granularity,
    )
    purchases_map = _bucket_totals(
        PurchaseLine.objects.filter(
            purchase__store=store,
            purchase__created_at__gte=start,
            purchase__created_at__lte=end,
        ),
        "purchase__created_at",
        cost_expr,
        granularity,
    )

    labels = sorted(set(sales_map) | set(payments_map) | set(purchases_map))
    sales = []
    payments = []
    purchases = []
    profit_cash = []
    profit_operating = []

    for label in labels:
        s = sales_map.get(label, 0.0)
        p = payments_map.get(label, 0.0)
        c = purchases_map.get(label, 0.0)
        sales.append(s)
        payments.append(p)
        purchases.append(c)
        profit_cash.append(s - p)
        profit_operating.append(s - c)

    return {
        "labels": labels,
        "sales": sales,
        "payments": payments,
        "purchases": purchases,
        "profit_cash": profit_cash,
        "profit_operating": profit_operating,
    }


def _confirmed_sale_lines(store, start, end):
    return SaleLine.objects.filter(
        sale__store=store,
        sale__status=Sale.Status.CONFIRMED,
        sale__created_at__gte=start,
        sale__created_at__lte=end,
    )


def _format_bucket_label(bucket, granularity: str) -> str:
    if bucket is None:
        return ""
    if timezone.is_aware(bucket):
        bucket = timezone.localtime(bucket)
    if granularity == "year":
        return str(bucket.year)
    if granularity == "month":
        return f"{bucket.year}-{bucket.month:02d}"
    if hasattr(bucket, "date"):
        return bucket.date().isoformat()
    return str(bucket)


@login_required
def home(request):
    return render(request, "store_ops/home.html")


def _trunc_for_granularity(granularity: str, field: str = "sale__created_at"):
    if granularity == "month":
        return TruncMonth(field)
    if granularity == "year":
        return TruncYear(field)
    return TruncDay(field)


@login_required
def dashboard(request):
    store = _store(request)
    d_from, d_to = _parse_range(request)
    start, end = _range_bounds(d_from, d_to)
    metrics = _profit_totals(store, start, end)

    recent_sales = (
        Sale.objects.filter(
            store=store,
            status=Sale.Status.CONFIRMED,
            created_at__gte=start,
            created_at__lte=end,
        )
        .select_related("user")
        .order_by("-created_at")[:8]
    )
    recent_payments = (
        SupplierPayment.objects.filter(store=store, created_at__gte=start, created_at__lte=end)
        .select_related("supplier", "user")
        .order_by("-created_at")[:8]
    )

    return render(
        request,
        "store_ops/dashboard.html",
        {
            "range_from": d_from,
            "range_to": d_to,
            **metrics,
            "recent_sales": recent_sales,
            "recent_payments": recent_payments,
        },
    )


@login_required
@require_GET
def api_profit_series(request):
    store = _store(request)
    d_from, d_to = _parse_range(request)
    granularity = request.GET.get("granularity", "day")
    start, end = _range_bounds(d_from, d_to)
    data = _profit_series(store, start, end, granularity)
    totals = _profit_totals(store, start, end)
    return JsonResponse(
        {
            **data,
            "granularity": granularity,
            "totals": {
                "sales": float(totals["sales_total"]),
                "payments": float(totals["payments_total"]),
                "purchases": float(totals["purchases_total"]),
                "net_cash": float(totals["net_cash"]),
                "net_operating": float(totals["net_operating"]),
            },
        }
    )


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
        formset = SaleLineFormSet(request.POST, prefix="lines")
        if form.is_valid() and formset.is_valid():
            filled = 0
            for f in formset.forms:
                d = getattr(f, "cleaned_data", None) or {}
                if d.get("DELETE"):
                    continue
                if d.get("product"):
                    filled += 1
            if filled < 1:
                messages.error(request, "Agregue al menos una línea de producto (escaneo o manual).")
            else:
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
        formset = SaleLineFormSet(prefix="lines")
    return render(request, "store_ops/sale_form.html", {"form": form, "formset": formset})


@login_required
def purchase_create(request):
    store = _store(request)
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        formset = PurchaseLineFormSet(request.POST, prefix="lines")
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
        formset = PurchaseLineFormSet(prefix="lines")
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


def _stock_rows(store, low_only: bool = False):
    """Inventory rows: product, quantity, and reorder minimum."""
    if low_only:
        rows = []
        for product in Product.objects.filter(reorder_min__gt=0).order_by("name"):
            qty = product.stock_quantity(store)
            if qty <= product.reorder_min:
                rows.append(
                    {
                        "product": product,
                        "quantity": qty,
                        "reorder_min": product.reorder_min,
                        "is_low": True,
                    }
                )
        return rows

    rows = []
    for level in (
        StockLevel.objects.filter(store=store)
        .select_related("product")
        .order_by("product__name")
    ):
        product = level.product
        rows.append(
            {
                "product": product,
                "quantity": level.quantity,
                "reorder_min": product.reorder_min,
                "is_low": bool(product.reorder_min and level.quantity <= product.reorder_min),
            }
        )
    return rows


@login_required
def stock_list(request):
    store = _store(request)
    low_only = request.GET.get("low") in ("1", "true", "yes")
    rows = _stock_rows(store, low_only=low_only)
    return render(
        request,
        "store_ops/stock_list.html",
        {"rows": rows, "low_only": low_only},
    )
