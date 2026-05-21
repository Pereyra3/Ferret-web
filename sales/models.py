from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce


class Sale(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"
        MIXED = "mixed", "Mixto"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        CONFIRMED = "confirmed", "Confirmada"

    store = models.ForeignKey("core.Store", on_delete=models.PROTECT, verbose_name="Store")
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
    amount_tendered = models.DecimalField(
        "Amount tendered",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cash received from customer (confirmed cash sales).",
    )
    change_amount = models.DecimalField(
        "Change given",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Change returned (cash sales).",
    )
    stock_applied = models.BooleanField("Stock applied", default=False)

    class Meta:
        db_table = "store_ops_sale"
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
            s=Coalesce(
                Sum(line_total),
                Value(0, output_field=DecimalField(max_digits=20, decimal_places=4)),
            )
        )
        return Decimal(agg["s"] or 0)

    @property
    def is_draft(self) -> bool:
        return self.status == self.Status.DRAFT


class SaleLine(models.Model):
    sale = models.ForeignKey(
        Sale,
        related_name="lines",
        on_delete=models.CASCADE,
        verbose_name="Sale",
    )
    product = models.ForeignKey(
        "warehouse.Product",
        on_delete=models.PROTECT,
        verbose_name="Product",
    )
    quantity = models.DecimalField("Quantity", max_digits=14, decimal_places=3)
    unit_price = models.DecimalField("Unit price", max_digits=14, decimal_places=2)

    class Meta:
        db_table = "store_ops_saleline"
        verbose_name = "Sale line"
        verbose_name_plural = "Sale lines"

    @property
    def line_total(self):
        return Decimal(self.quantity) * Decimal(self.unit_price)


class DayClose(models.Model):
    store = models.ForeignKey("core.Store", on_delete=models.CASCADE, verbose_name="Store")
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
        db_table = "store_ops_dayclose"
        verbose_name = "Day close"
        verbose_name_plural = "Day closes"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "date"],
                name="uniq_dayclose_store_date",
            ),
        ]

    def __str__(self) -> str:
        return f"Close {self.store} {self.date}"
