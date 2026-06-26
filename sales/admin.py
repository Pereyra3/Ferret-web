from django.contrib import admin

from sales.models import DayClose, Quote, QuoteLine, Sale, SaleLine


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
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
        "card_amount",
        "amount_tendered",
        "change_amount",
        "stock_applied",
    )
    list_filter = ("store", "status", "payment_method")
    inlines = [SaleLineInline]


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store",
        "user",
        "created_at",
        "customer_name",
        "valid_until",
    )
    list_filter = ("store",)
    search_fields = ("customer_name", "notes")
    inlines = [QuoteLineInline]


@admin.register(DayClose)
class DayCloseAdmin(admin.ModelAdmin):
    list_display = ("store", "date", "closed_at", "created_by")
