from django.contrib import admin

from sales.models import DayClose, Sale, SaleLine


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store",
        "user",
        "created_at",
        "payment_method",
        "status",
        "amount_tendered",
        "change_amount",
        "stock_applied",
    )
    list_filter = ("store", "status", "payment_method")
    inlines = [SaleLineInline]


@admin.register(DayClose)
class DayCloseAdmin(admin.ModelAdmin):
    list_display = ("store", "date", "closed_at", "created_by")
