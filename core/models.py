from django.conf import settings
from django.db import models


class Store(models.Model):
    name = models.CharField("Name", max_length=120)
    code = models.SlugField("Code", unique=True)
    location = models.CharField("Location", max_length=255, blank=True)
    phone = models.CharField("Phone", max_length=40, blank=True)
    rfc = models.CharField("RFC", max_length=20, blank=True)
    is_default = models.BooleanField("Default store", default=False)
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="assigned_stores",
        verbose_name="Assigned users",
        help_text="Users who can see and operate this store only.",
    )

    class Meta:
        db_table = "store_ops_store"
        verbose_name = "Store"
        verbose_name_plural = "Stores"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
