from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce


class Store(models.Model):
    name = models.CharField("Name", max_length=120)
    code = models.SlugField("Code", unique=True)
    is_default = models.BooleanField("Default store", default=False)

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


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
        agg = qs.aggregate(t=Coalesce(Sum(line_total), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4))))
        return agg["t"] or Decimal(0)

    def payments_total(self, store=None):
        qs = SupplierPayment.objects.filter(supplier=self)
        if store is not None:
            qs = qs.filter(store=store)
        agg = qs.aggregate(
            t=Coalesce(Sum("amount"), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)))
        )
        return agg["t"] or Decimal(0)

    def balance(self, store=None):
        """Positive = we owe supplier (rough accounts payable)."""
        purchases = Decimal(self.purchases_total(store) or 0)
        payments = Decimal(self.payments_total(store) or 0)
        return self.opening_balance + purchases - payments


class Product(models.Model):
    sku = models.CharField("SKU / barcode", max_length=64, unique=True)
    name = models.CharField("Name", max_length=255)
    category = models.CharField("Category", max_length=120, blank=True)
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

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.sku} — {self.name}"

    def stock_quantity(self, store):
        row = StockLevel.objects.filter(store=store, product=self).first()
        return row.quantity if row else 0


class StockLevel(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Store")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Product")
    quantity = models.DecimalField("Quantity", max_digits=14, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Stock level"
        verbose_name_plural = "Stock levels"
        constraints = [
            models.UniqueConstraint(fields=["store", "product"], name="uniq_stock_store_product"),
        ]

    def __str__(self) -> str:
        return f"{self.store} / {self.product}: {self.quantity}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Compra proveedor"
        SALE = "sale", "Venta"
        ADJUSTMENT = "adjustment", "Ajuste manual"
        SALE_VOID = "sale_void", "Reversión venta"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Store")
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
        verbose_name = "Stock movement"
        verbose_name_plural = "Stock movements"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_reason_display()} {self.quantity_delta} {self.product}"


class Sale(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"
        MIXED = "mixed", "Mixto"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        CONFIRMED = "confirmed", "Confirmada"

    store = models.ForeignKey(Store, on_delete=models.PROTECT, verbose_name="Store")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="User",
    )
    created_at = models.DateTimeField("Date", auto_now_add=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    payment_method = models.CharField(
        "Payment method",
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    notes = models.CharField("Notes", max_length=500, blank=True)
    stock_applied = models.BooleanField("Stock applied", default=False)

    class Meta:
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Sale #{self.pk} {self.store}"

    def total(self):
        line_total = ExpressionWrapper(
            F("quantity") * F("unit_price"),
            output_field=DecimalField(max_digits=20, decimal_places=4),
        )
        agg = self.lines.aggregate(
            s=Coalesce(Sum(line_total), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)))
        )
        return Decimal(agg["s"] or 0)


class SaleLine(models.Model):
    sale = models.ForeignKey(
        Sale,
        related_name="lines",
        on_delete=models.CASCADE,
        verbose_name="Sale",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Product")
    quantity = models.DecimalField("Quantity", max_digits=14, decimal_places=3)
    unit_price = models.DecimalField("Unit price", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Sale line"
        verbose_name_plural = "Sale lines"

    @property
    def line_total(self):
        from decimal import Decimal

        return Decimal(self.quantity) * Decimal(self.unit_price)


class Purchase(models.Model):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, verbose_name="Store")
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
            s=Coalesce(Sum(line_total), Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)))
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
        verbose_name = "Purchase line"
        verbose_name_plural = "Purchase lines"


class SupplierPayment(models.Model):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, verbose_name="Store")
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
        verbose_name = "Supplier payment"
        verbose_name_plural = "Supplier payments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.supplier} {self.amount}"


class DayClose(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Store")
    date = models.DateField("Business date")
    closed_at = models.DateTimeField(auto_now_add=True)
    export_pdf_path = models.CharField(max_length=500, blank=True)
    export_csv_path = models.CharField(max_length=500, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Day close"
        verbose_name_plural = "Day closes"
        constraints = [
            models.UniqueConstraint(fields=["store", "date"], name="uniq_dayclose_store_date"),
        ]

    def __str__(self) -> str:
        return f"Close {self.store} {self.date}"
