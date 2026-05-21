from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.store_access import allowed_store_ids
from sales.models import Sale
from warehouse.models import Product, Purchase, StockLevel, StockMovement, StockTransfer


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
def apply_adjustment(
    store, product: Product, quantity_delta: Decimal, user, *, reference="adjustment"
):
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
        reference=reference,
        created_by=user,
    )


def user_can_accept_transfer(user, transfer: StockTransfer) -> bool:
    """Requires Django ``change_stocktransfer`` and assignment to the receiving store."""
    if not user.has_perm("warehouse.change_stocktransfer"):
        return False
    if user.is_superuser:
        return True
    return transfer.to_store_id in allowed_store_ids(user)


@transaction.atomic
def reject_transfer(transfer: StockTransfer, user):
    """Reject a pending transfer (no stock movement)."""
    if transfer.status == StockTransfer.Status.REJECTED:
        return
    if transfer.status != StockTransfer.Status.PENDING:
        raise ValueError("Solo se pueden rechazar transferencias pendientes.")
    if not user_can_accept_transfer(user, transfer):
        raise ValueError(
            "No tiene permiso para rechazar transferencias en esta tienda."
        )
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.status != StockTransfer.Status.PENDING:
        raise ValueError("Solo se pueden rechazar transferencias pendientes.")
    transfer.status = StockTransfer.Status.REJECTED
    transfer.rejected_by = user
    transfer.rejected_at = timezone.now()
    transfer.save(update_fields=["status", "rejected_by", "rejected_at"])


@transaction.atomic
def accept_transfer(transfer: StockTransfer, user):
    """Accept a pending transfer and move stock."""
    if transfer.status == StockTransfer.Status.ACCEPTED and transfer.applied:
        return
    if transfer.status != StockTransfer.Status.PENDING:
        raise ValueError("Solo se pueden aceptar transferencias pendientes.")
    if not user_can_accept_transfer(user, transfer):
        raise ValueError(
            "No tiene permiso para aceptar transferencias en esta tienda."
        )
    apply_transfer(transfer, user)


@transaction.atomic
def apply_transfer(transfer: StockTransfer, user):
    """Move stock from one store to another after acceptance."""
    if transfer.status == StockTransfer.Status.REJECTED:
        raise ValueError("La transferencia fue rechazada.")
    if transfer.applied:
        return
    if transfer.from_store_id == transfer.to_store_id:
        raise ValueError("La tienda origen y destino deben ser distintas.")
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.applied:
        return
    if transfer.status != StockTransfer.Status.PENDING:
        raise ValueError("Solo se puede aplicar una transferencia pendiente.")
    ref = f"transfer:{transfer.pk}"
    for line in transfer.lines.select_related("product"):
        qty = Decimal(line.quantity)
        if qty <= 0:
            raise ValueError(f"Cantidad inválida para {line.product.sku}.")
        try:
            from_sl = StockLevel.objects.select_for_update().get(
                store=transfer.from_store, product=line.product
            )
        except StockLevel.DoesNotExist as exc:
            raise ValueError(
                f"Sin existencia en origen: {line.product.sku}."
            ) from exc
        available = Decimal(from_sl.quantity)
        if available < qty:
            raise ValueError(
                f"Stock insuficiente en {transfer.from_store}: "
                f"{line.product.sku} (hay {available}, se piden {qty})."
            )
        from_sl.quantity = available - qty
        from_sl.save()
        StockMovement.objects.create(
            store=transfer.from_store,
            product=line.product,
            quantity_delta=-qty,
            reason=StockMovement.Reason.TRANSFER_OUT,
            reference=ref,
            created_by=user,
        )
        to_sl, _ = StockLevel.objects.select_for_update().get_or_create(
            store=transfer.to_store,
            product=line.product,
            defaults={"quantity": Decimal(0)},
        )
        to_sl.quantity = Decimal(to_sl.quantity) + qty
        to_sl.save()
        StockMovement.objects.create(
            store=transfer.to_store,
            product=line.product,
            quantity_delta=qty,
            reason=StockMovement.Reason.TRANSFER_IN,
            reference=ref,
            created_by=user,
        )
    now = timezone.now()
    transfer.applied = True
    transfer.status = StockTransfer.Status.ACCEPTED
    transfer.accepted_by = user
    transfer.accepted_at = now
    transfer.save(
        update_fields=["applied", "status", "accepted_by", "accepted_at"]
    )
