from django.contrib import admin

from warehouse.models import (
    Product,
    Purchase,
    PurchaseLine,
    StockLevel,
    StockMovement,
    StockTransfer,
    StockTransferLine,
    Supplier,
    SupplierPayment,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "opening_balance")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "department",
        "location",
        "category",
        "list_price",
        "reorder_min",
        "stock_max",
    )
    list_filter = ("department", "location")
    search_fields = ("sku", "name")


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "store", "created_at", "stock_applied")
    inlines = [PurchaseLineInline]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "store", "amount", "created_at")


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ("store", "product", "quantity")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "store", "product", "quantity_delta", "reason", "reference")


class StockTransferLineInline(admin.TabularInline):
    model = StockTransferLine
    extra = 0


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "from_store",
        "to_store",
        "status",
        "created_at",
        "applied",
        "user",
        "accepted_by",
    )
    list_filter = ("status", "from_store", "to_store")
    readonly_fields = (
        "status",
        "applied",
        "accepted_by",
        "accepted_at",
        "rejected_by",
        "rejected_at",
        "created_at",
    )
    inlines = [StockTransferLineInline]
