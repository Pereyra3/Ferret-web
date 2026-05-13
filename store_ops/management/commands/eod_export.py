from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from store_ops.models import Store
from store_ops.services.eod import run_eod


class Command(BaseCommand):
    help = "Exporta cierre del día: solo ventas (PDF + CSV) para el sistema corporativo."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="AAAA-MM-DD (default: hoy local)")
        parser.add_argument("--store-code", type=str, default="", help="Código de tienda (default: DEFAULT_STORE_CODE)")
        parser.add_argument("--force", action="store_true", help="Regenerar si ya existe cierre")
        parser.add_argument("--notes", type=str, default="", help="Notas en el PDF")

    def handle(self, *args, **options):
        code = options["store_code"] or getattr(settings, "DEFAULT_STORE_CODE", "principal")
        store = Store.objects.filter(code=code).first()
        if not store:
            raise SystemExit(f"No existe tienda con código {code}. Ejecute: python manage.py setup_defaults")

        d = (
            date.fromisoformat(options["date"])
            if options["date"]
            else timezone.localdate()
        )

        User = get_user_model()
        user = User.objects.filter(is_superuser=True).order_by("id").first()

        close, wrote = run_eod(store, d, user, notes=options.get("notes") or "", force=options["force"])
        if wrote:
            self.stdout.write(self.style.SUCCESS(f"Cierre generado: {close.export_pdf_path}"))
        else:
            self.stdout.write(self.style.WARNING("Ya existía cierre (use --force para regenerar)."))
