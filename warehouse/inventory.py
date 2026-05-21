"""Inventory list helpers (used by stock CBVs)."""

from decimal import Decimal

from django.db.models import Sum

from warehouse.models import Product, StockLevel


def aggregate_stock_quantity(product, store_ids):
    agg = StockLevel.objects.filter(
        product=product, store_id__in=store_ids
    ).aggregate(total=Sum("quantity"))
    return Decimal(agg["total"] or 0)


def suggested_restock_multi(product, store_ids) -> Decimal:
    current = aggregate_stock_quantity(product, store_ids)
    stock_max = product.stock_max
    if not stock_max or stock_max <= 0:
        return Decimal(0)
    need = Decimal(stock_max) - current
    return need if need > 0 else Decimal(0)


def inventory_filters(request):
    department = (request.GET.get("department") or "").strip()
    location = (request.GET.get("location") or "").strip()
    return department, location


def apply_product_filters(qs, department="", location=""):
    if department:
        qs = qs.filter(department=department)
    if location:
        qs = qs.filter(location=location)
    return qs


def inventory_filter_options():
    departments = list(
        Product.objects.exclude(department="")
        .values_list("department", flat=True)
        .distinct()
        .order_by("department")
    )
    locations = list(
        Product.objects.exclude(location="")
        .values_list("location", flat=True)
        .distinct()
        .order_by("location")
    )
    return departments, locations


def inventory_filter_query(department, location):
    params = []
    if department:
        params.append(f"department={department}")
    if location:
        params.append(f"location={location}")
    return f"?{'&'.join(params)}" if params else ""


def stock_row(product, quantity, store):
    qty = Decimal(quantity)
    reorder_min = product.reorder_min
    stock_max = product.stock_max
    suggested = product.suggested_restock(store)
    return {
        "product": product,
        "quantity": qty,
        "reorder_min": reorder_min,
        "stock_max": stock_max,
        "suggested": suggested,
        "is_low": bool(reorder_min and qty <= reorder_min),
        "below_max": bool(stock_max and suggested > 0),
    }


def stock_rows(
    store_or_ids,
    *,
    low_only: bool = False,
    suggested_only: bool = False,
    department: str = "",
    location: str = "",
):
    if isinstance(store_or_ids, (list, tuple)):
        store_ids = list(store_or_ids)
        multi = len(store_ids) != 1
    else:
        store_ids = [store_or_ids.pk]
        multi = False

    if suggested_only:
        rows = []
        qs = apply_product_filters(
            Product.objects.filter(stock_max__gt=0).order_by("name"),
            department,
            location,
        )
        for product in qs:
            if multi:
                suggested = suggested_restock_multi(product, store_ids)
                qty = aggregate_stock_quantity(product, store_ids)
            else:
                store = store_or_ids if not isinstance(store_or_ids, (list, tuple)) else None
                from core.models import Store

                store = Store.objects.get(pk=store_ids[0])
                suggested = product.suggested_restock(store)
                qty = product.stock_quantity(store)
            if suggested > 0:
                rows.append(stock_row(product, qty, store_ids[0] if store_ids else None))
        return rows

    if low_only:
        rows = []
        qs = apply_product_filters(
            Product.objects.filter(reorder_min__gt=0).order_by("name"),
            department,
            location,
        )
        for product in qs:
            if multi:
                qty = aggregate_stock_quantity(product, store_ids)
            else:
                from core.models import Store

                store = Store.objects.get(pk=store_ids[0])
                qty = product.stock_quantity(store)
            if qty <= product.reorder_min:
                rows.append(stock_row(product, qty, store_ids[0]))
        return rows

    rows = []
    levels = (
        StockLevel.objects.filter(store_id__in=store_ids)
        .select_related("product")
        .order_by("product__name")
    )
    if department:
        levels = levels.filter(product__department=department)
    if location:
        levels = levels.filter(product__location=location)
    if multi:
        seen = {}
        for level in levels:
            pid = level.product_id
            if pid not in seen:
                seen[pid] = {"product": level.product, "qty": Decimal(0)}
            seen[pid]["qty"] += Decimal(level.quantity)
        for data in sorted(seen.values(), key=lambda x: x["product"].name):
            rows.append(stock_row(data["product"], data["qty"], store_ids[0]))
    else:
        for level in levels:
            rows.append(stock_row(level.product, level.quantity, store_ids[0]))
    return rows
