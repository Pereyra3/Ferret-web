from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce


class Supplier(models.Model):
    name = models.CharField("Name", max_length=200)
    opening_balance = models.DecimalField(
        "Opening balance (payable)",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Positive = amount owed before this system.",
    )

    class Meta:
        db_table = "store_ops_supplier"
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def purchases_total(self, store=None):
        qs = PurchaseLine.objects.filter(purchase__supplier=self)
        if store is not None:
            qs = qs.filter(purchase__store=store)
        line_total = ExpressionWrapper(
            F("quantity") * F("unit_cost"),
            output_field=DecimalField(max_digits=20, decimal_places=4),
        )
        agg = qs.aggregate(
            t=Coalesce(
                Sum(line_total),
                Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)),
            )
        )
        return agg["t"] or Decimal(0)

    def payments_total(self, store=None):
        qs = SupplierPayment.objects.filter(supplier=self)
        if store is not None:
            qs = qs.filter(store=store)
        agg = qs.aggregate(
            t=Coalesce(
                Sum("amount"),
                Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)),
            )
        )
        return agg["t"] or Decimal(0)

    def balance(self, store=None):
        purchases = Decimal(self.purchases_total(store) or 0)
        payments = Decimal(self.payments_total(store) or 0)
        return self.opening_balance + purchases - payments


class Product(models.Model):
    sku = models.CharField("SKU / barcode", max_length=64, unique=True)
    name = models.CharField("Name", max_length=255)
    category = models.CharField("Category", max_length=120, blank=True)
    department = models.CharField(
        "Department",
        max_length=120,
        blank=True,
        help_text="Store area or department (e.g. plumbing, electrical).",
    )
    location = models.CharField(
        "Storage location",
        max_length=120,
        blank=True,
        help_text="Shelf, aisle, or bin in the warehouse.",
    )
    list_price = models.DecimalField(
        "Suggested list price",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Used when scanning at POS; can be overridden on the line.",
    )
    reorder_min = models.DecimalField(
        "Reorder alert minimum",
        max_digits=14,
        decimal_places=3,
        default=0,
    )
    stock_max = models.DecimalField(
        "Stock maximum",
        max_digits=14,
        decimal_places=3,
        default=0,
        help_text="Target on-hand quantity. 0 = no cap configured.",
    )

    class Meta:
        db_table = "store_ops_product"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.sku} — {self.name}"

    def stock_quantity(self, store):
        row = StockLevel.objects.filter(store=store, product=self).first()
        return row.quantity if row else 0

    def suggested_restock(self, store) -> Decimal:
        cap = Decimal(self.stock_max or 0)
        if cap <= 0:
            return Decimal(0)
        current = Decimal(self.stock_quantity(store))
        if current >= cap:
            return Decimal(0)
        return cap - current


class StockLevel(models.Model):
    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, verbose_name="Store")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Product")
    quantity = models.DecimalField("Quantity", max_digits=14, decimal_places=3, default=0)

    class Meta:
        db_table = "store_ops_stocklevel"
        verbose_name = "Stock level"
        verbose_name_plural = "Stock levels"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "product"],
                name="uniq_stock_store_product",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.store} / {self.product}: {self.quantity}"


class StockTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente de aceptación"
        ACCEPTED = "accepted", "Aceptada"
        REJECTED = "rejected", "Rechazada"

    from_store = models.ForeignKey(
        "core.Store",
        on_delete=models.PROTECT,
        related_name="transfers_out",
        verbose_name="From store",
    )
    to_store = models.ForeignKey(
        "core.Store",
        on_delete=models.PROTECT,
        related_name="transfers_in",
        verbose_name="To store",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_transfers_created",
        verbose_name="User",
    )
    notes = models.CharField("Notes", max_length=500, blank=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    applied = models.BooleanField("Applied", default=False)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_transfers_accepted",
        verbose_name="Accepted by",
    )
    accepted_at = models.DateTimeField("Accepted at", null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_transfers_rejected",
        verbose_name="Rejected by",
    )
    rejected_at = models.DateTimeField("Rejected at", null=True, blank=True)

    class Meta:
        db_table = "store_ops_stocktransfer"
        verbose_name = "Stock transfer"
        verbose_name_plural = "Stock transfers"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Transfer #{self.pk} {self.from_store} → {self.to_store}"


class StockTransferLine(models.Model):
    transfer = models.ForeignKey(
        StockTransfer,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Transfer",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Product")
    quantity = models.DecimalField("Quantity", max_digits=14, decimal_places=3)

    class Meta:
        db_table = "store_ops_stocktransferline"
        verbose_name = "Stock transfer line"
        verbose_name_plural = "Stock transfer lines"

    def __str__(self) -> str:
        return f"{self.product} × {self.quantity}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Compra proveedor"
        SALE = "sale", "Venta"
        ADJUSTMENT = "adjustment", "Ajuste manual"
        SALE_VOID = "sale_void", "Reversión venta"
        TRANSFER_OUT = "transfer_out", "Transferencia salida"
        TRANSFER_IN = "transfer_in", "Transferencia entrada"

    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, verbose_name="Store")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Product")
    quantity_delta = models.DecimalField("Quantity delta", max_digits=14, decimal_places=3)
    reason = models.CharField("Reason", max_length=20, choices=Reason.choices)
    reference = models.CharField("Reference", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="User",
    )

    class Meta:
        db_table = "store_ops_stockmovement"
        verbose_name = "Stock movement"
        verbose_name_plural = "Stock movements"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_reason_display()} {self.quantity_delta} {self.product}"


class Purchase(models.Model):
    store = models.ForeignKey("core.Store", on_delete=models.PROTECT, verbose_name="Store")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Supplier")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="User",
    )
    reference = models.CharField("Reference / invoice", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    stock_applied = models.BooleanField("Stock applied", default=False)

    class Meta:
        db_table = "store_ops_purchase"
        verbose_name = "Supplier purchase"
        verbose_name_plural = "Supplier purchases"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Purchase #{self.pk} {self.supplier}"

    def total(self):
        line_total = ExpressionWrapper(
            F("quantity") * F("unit_cost"),
            output_field=DecimalField(max_digits=20, decimal_places=4),
        )
        agg = self.lines.aggregate(
            s=Coalesce(
                Sum(line_total),
                Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)),
            )
        )
        return Decimal(agg["s"] or 0)


class PurchaseLine(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        related_name="lines",
        on_delete=models.CASCADE,
        verbose_name="Purchase",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Product")
    quantity = models.DecimalField("Quantity", max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField("Unit cost", max_digits=14, decimal_places=2)

    class Meta:
        db_table = "store_ops_purchaseline"
        verbose_name = "Purchase line"
        verbose_name_plural = "Purchase lines"


class SupplierPayment(models.Model):
    store = models.ForeignKey("core.Store", on_delete=models.PROTECT, verbose_name="Store")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Supplier")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="User",
    )
    amount = models.DecimalField("Amount", max_digits=14, decimal_places=2)
    note = models.CharField("Note", max_length=500, blank=True)
    reference = models.CharField("Reference", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_ops_supplierpayment"
        verbose_name = "Supplier payment"
        verbose_name_plural = "Supplier payments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.supplier} {self.amount}"
