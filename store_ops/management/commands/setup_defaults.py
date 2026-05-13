from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from store_ops.models import Store


class Command(BaseCommand):
    help = "Crea carpeta data/, tienda por defecto y ajusta flags is_default."

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        data_dir = base / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        exports = Path(settings.EOD_EXPORT_DIR)
        exports.mkdir(parents=True, exist_ok=True)

        code = getattr(settings, "DEFAULT_STORE_CODE", "principal")
        store, created = Store.objects.get_or_create(
            code=code,
            defaults={"name": "Tienda principal", "is_default": True},
        )
        if not created:
            self.stdout.write(f"Tienda ya existía: {store}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Tienda creada: {store}"))

        Store.objects.exclude(pk=store.pk).update(is_default=False)
        if not store.is_default:
            store.is_default = True
            store.save(update_fields=["is_default"])

        self.stdout.write("Listo. Cree un superusuario: python manage.py createsuperuser")
