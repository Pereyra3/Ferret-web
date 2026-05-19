from django.contrib import admin

from .models import (
    DayClose,
    Product,
    Purchase,
    PurchaseLine,
    Sale,
    SaleLine,
    StockLevel,
    StockMovement,
    Store,
    Supplier,
    SupplierPayment,
)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_default")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "opening_balance")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "list_price", "reorder_min")
    search_fields = ("sku", "name")


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "user", "created_at", "payment_method", "status", "stock_applied")
    list_filter = ("store", "status", "payment_method")
    inlines = [SaleLineInline]


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


@admin.register(DayClose)
class DayCloseAdmin(admin.ModelAdmin):
    list_display = ("store", "date", "closed_at", "created_by")
