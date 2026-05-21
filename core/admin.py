from django.contrib import admin

from core.models import Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "phone", "is_default")
    filter_horizontal = ("assigned_users",)
    fieldsets = (
        (None, {"fields": ("name", "code", "is_default")}),
        ("Ticket / contacto", {"fields": ("location", "phone", "rfc")}),
        ("Acceso", {"fields": ("assigned_users",)}),
    )
