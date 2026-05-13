from decimal import Decimal

from django.db import transaction

from ..models import Product, Purchase, Sale, StockLevel, StockMovement


@transaction.atomic
def apply_sale(sale: Sale, user):
    """Decrement stock for confirmed sale; idempotent via sale.stock_applied."""
    if sale.status != Sale.Status.CONFIRMED:
        return
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.stock_applied:
        return
    for line in sale.lines.select_related("product"):
        product = line.product
        sl, _ = StockLevel.objects.select_for_update().get_or_create(
            store=sale.store,
            product=product,
            defaults={"quantity": Decimal(0)},
        )
        sl.quantity = Decimal(sl.quantity) - Decimal(line.quantity)
        sl.save()
        StockMovement.objects.create(
            store=sale.store,
            product=product,
            quantity_delta=-Decimal(line.quantity),
            reason=StockMovement.Reason.SALE,
            reference=f"sale:{sale.pk}",
            created_by=user,
        )
    sale.stock_applied = True
    sale.save(update_fields=["stock_applied"])


@transaction.atomic
def apply_purchase(purchase, user):
    if purchase.stock_applied:
        return
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.stock_applied:
        return
    for line in purchase.lines.select_related("product"):
        product = line.product
        sl, _ = StockLevel.objects.select_for_update().get_or_create(
            store=purchase.store,
            product=product,
            defaults={"quantity": Decimal(0)},
        )
        sl.quantity = Decimal(sl.quantity) + Decimal(line.quantity)
        sl.save()
        StockMovement.objects.create(
            store=purchase.store,
            product=product,
            quantity_delta=Decimal(line.quantity),
            reason=StockMovement.Reason.PURCHASE,
            reference=f"purchase:{purchase.pk}",
            created_by=user,
        )
    purchase.stock_applied = True
    purchase.save(update_fields=["stock_applied"])


@transaction.atomic
def apply_adjustment(store, product: Product, quantity_delta: Decimal, user):
    sl, _ = StockLevel.objects.select_for_update().get_or_create(
        store=store,
        product=product,
        defaults={"quantity": Decimal(0)},
    )
    sl.quantity = Decimal(sl.quantity) + Decimal(quantity_delta)
    sl.save()
    StockMovement.objects.create(
        store=store,
        product=product,
        quantity_delta=Decimal(quantity_delta),
        reason=StockMovement.Reason.ADJUSTMENT,
        reference="adjustment",
        created_by=user,
    )
