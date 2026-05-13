from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce


class Store(models.Model):
    name = models.CharField("Nombre", max_length=120)
    code = models.SlugField("Código", unique=True)
    is_default = models.BooleanField("Tienda por defecto", default=False)

    class Meta:
        verbose_name = "Tienda"
        verbose_name_plural = "Tiendas"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Supplier(models.Model):
    name = models.CharField("Proveedor", max_length=200)
    opening_balance = models.DecimalField(
        "Saldo inicial (deuda)",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Positivo = adeudo previo a este sistema.",
    )

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
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
    sku = models.CharField("SKU / código", max_length=64, unique=True)
    name = models.CharField("Nombre", max_length=255)
    category = models.CharField("Categoría", max_length=120, blank=True)
    reorder_min = models.DecimalField(
        "Stock mínimo alerta",
        max_digits=14,
        decimal_places=3,
        default=0,
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.sku} — {self.name}"

    def stock_quantity(self, store):
        row = StockLevel.objects.filter(store=store, product=self).first()
        return row.quantity if row else 0


class StockLevel(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Tienda")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Producto")
    quantity = models.DecimalField("Cantidad", max_digits=14, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Existencia"
        verbose_name_plural = "Existencias"
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

    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Tienda")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Producto")
    quantity_delta = models.DecimalField("Delta cantidad", max_digits=14, decimal_places=3)
    reason = models.CharField("Motivo", max_length=20, choices=Reason.choices)
    reference = models.CharField("Referencia", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Usuario",
    )

    class Meta:
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"
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

    store = models.ForeignKey(Store, on_delete=models.PROTECT, verbose_name="Tienda")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Usuario",
    )
    created_at = models.DateTimeField("Fecha", auto_now_add=True)
    status = models.CharField(
        "Estado",
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    payment_method = models.CharField(
        "Forma de pago",
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    notes = models.CharField("Notas", max_length=500, blank=True)
    stock_applied = models.BooleanField("Inventario aplicado", default=False)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Venta #{self.pk} {self.store}"

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
        verbose_name="Venta",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Producto")
    quantity = models.DecimalField("Cantidad", max_digits=14, decimal_places=3)
    unit_price = models.DecimalField("Precio unit.", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Línea de venta"
        verbose_name_plural = "Líneas de venta"

    @property
    def line_total(self):
        from decimal import Decimal

        return Decimal(self.quantity) * Decimal(self.unit_price)


class Purchase(models.Model):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, verbose_name="Tienda")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Proveedor")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Usuario",
    )
    reference = models.CharField("Referencia / factura", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    stock_applied = models.BooleanField("Inventario aplicado", default=False)

    class Meta:
        verbose_name = "Compra a proveedor"
        verbose_name_plural = "Compras a proveedor"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Compra #{self.pk} {self.supplier}"

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
        verbose_name="Compra",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Producto")
    quantity = models.DecimalField("Cantidad", max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField("Costo unit.", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Línea de compra"
        verbose_name_plural = "Líneas de compra"


class SupplierPayment(models.Model):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, verbose_name="Tienda")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Proveedor")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Usuario",
    )
    amount = models.DecimalField("Monto", max_digits=14, decimal_places=2)
    note = models.CharField("Nota", max_length=500, blank=True)
    reference = models.CharField("Referencia", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pago a proveedor"
        verbose_name_plural = "Pagos a proveedor"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Pago {self.supplier} {self.amount}"


class DayClose(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Tienda")
    date = models.DateField("Día operativo")
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
        verbose_name = "Cierre de día"
        verbose_name_plural = "Cierres de día"
        constraints = [
            models.UniqueConstraint(fields=["store", "date"], name="uniq_dayclose_store_date"),
        ]

    def __str__(self) -> str:
        return f"Cierre {self.store} {self.date}"
