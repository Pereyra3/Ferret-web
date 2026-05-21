from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncYear
from django.utils import timezone

from core.utils import parse_date_range, range_bounds
from sales.models import Sale, SaleLine
from warehouse.models import PurchaseLine, SupplierPayment

def line_total_expr():
    return ExpressionWrapper(
        F("quantity") * F("unit_price"),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    )

def cost_line_expr():
    return ExpressionWrapper(
        F("quantity") * F("unit_cost"),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    )

def zero_decimal():
    return Value(0, output_field=DecimalField(max_digits=20, decimal_places=4))

def bucket_totals(qs, trunc_field: str, sum_expr, granularity: str):
    trunc = trunc_for_granularity(granularity, trunc_field)
    rows = (
        qs.annotate(bucket=trunc)
        .values("bucket")
        .annotate(total=Coalesce(Sum(sum_expr), zero_decimal()))
        .order_by("bucket")
    )
    out = {}
    for row in rows:
        label = format_bucket_label(row["bucket"], granularity)
        out[label] = float(row["total"] or 0)
    return out

def profit_totals(store_ids, start, end):
    line_total = line_total_expr()
    cost_expr = cost_line_expr()

    sales_total = Decimal(
        confirmed_sale_lines(store_ids, start, end).aggregate(
            t=Coalesce(Sum(line_total), zero_decimal())
        )["t"]
        or 0
    )
    payments_total = Decimal(
        SupplierPayment.objects.filter(
            store_id__in=store_ids,
            created_at__gte=start,
            created_at__lte=end,
        ).aggregate(t=Coalesce(Sum("amount"), zero_decimal()))["t"]
        or 0
    )
    purchases_total = Decimal(
        PurchaseLine.objects.filter(
            purchase__store_id__in=store_ids,
            purchase__created_at__gte=start,
            purchase__created_at__lte=end,
        ).aggregate(t=Coalesce(Sum(cost_expr), zero_decimal()))["t"]
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

def profit_series(store_ids, start, end, granularity: str):
    line_total = line_total_expr()
    cost_expr = cost_line_expr()

    sales_map = bucket_totals(
        confirmed_sale_lines(store_ids, start, end),
        "sale__created_at",
        line_total,
        granularity,
    )
    payments_map = bucket_totals(
        SupplierPayment.objects.filter(
            store_id__in=store_ids, created_at__gte=start, created_at__lte=end
        ),
        "created_at",
        F("amount"),
        granularity,
    )
    purchases_map = bucket_totals(
        PurchaseLine.objects.filter(
            purchase__store_id__in=store_ids,
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

def confirmed_sale_lines(store_ids, start, end):
    return SaleLine.objects.filter(
        sale__store_id__in=store_ids,
        sale__status=Sale.Status.CONFIRMED,
        sale__created_at__gte=start,
        sale__created_at__lte=end,
    )

def format_bucket_label(bucket, granularity: str) -> str:
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

def trunc_for_granularity(granularity: str, field: str = "sale__created_at"):
    if granularity == "month":
        return TruncMonth(field)
    if granularity == "year":
        return TruncYear(field)
    return TruncDay(field)

