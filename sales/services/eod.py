"""End-of-day export: sales only (no inventory) for legacy system transcription."""
import csv
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from core.money import format_mxn
from sales.models import DayClose, Sale, SaleLine


def _local_date_bounds(d: date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, time.min), tz)
    end = timezone.make_aware(datetime.combine(d, time.max), tz)
    return start, end


def iter_sale_lines_for_day(store, d: date):
    start, end = _local_date_bounds(d)
    return (
        SaleLine.objects.filter(
            sale__store=store,
            sale__status=Sale.Status.CONFIRMED,
            sale__created_at__gte=start,
            sale__created_at__lte=end,
        )
        .select_related("sale", "product")
        .order_by("sale_id", "id")
    )


def build_sales_summary(store, d: date):
    lines = list(iter_sale_lines_for_day(store, d))
    total = Decimal(0)
    by_payment = {}
    for line in lines:
        t = Decimal(line.quantity) * Decimal(line.unit_price)
        total += t
        pm = line.sale.get_payment_method_display()
        by_payment[pm] = by_payment.get(pm, Decimal(0)) + t
    return {
        "lines": lines,
        "total": total,
        "by_payment": by_payment,
        "count_sales": len({ln.sale_id for ln in lines}),
    }


def write_csv(path: Path, store, d: date):
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_sales_summary(store, d)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "sale_id",
                "fecha_hora",
                "forma_pago",
                "sku",
                "producto",
                "cantidad",
                "precio_unit",
                "importe_linea",
            ]
        )
        for line in summary["lines"]:
            w.writerow(
                [
                    line.sale_id,
                    timezone.localtime(line.sale.created_at).isoformat(),
                    line.sale.get_payment_method_display(),
                    line.product.sku,
                    line.product.name,
                    str(line.quantity),
                    str(line.unit_price),
                    str(Decimal(line.quantity) * Decimal(line.unit_price)),
                ]
            )
        w.writerow([])
        w.writerow(["TOTAL_DIA", str(summary["total"])])
        for pm, val in summary["by_payment"].items():
            w.writerow([f"TOTAL_{pm}", str(val)])


def write_pdf(path: Path, store, d: date, notes: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_sales_summary(store, d)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Cierre de ventas — {store.name} — {d.isoformat()}")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Solo ventas para transcribir al sistema corporativo (sin inventario).")
    y -= 18
    c.drawString(50, y, f"Tickets / ventas con líneas: {summary['count_sales']}")
    y -= 16
    c.drawString(50, y, f"Total del día: {format_mxn(summary['total'])}")
    y -= 16
    for pm, val in summary["by_payment"].items():
        c.drawString(50, y, f"Total {pm}: {format_mxn(val)}")
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
    if notes:
        y -= 10
        c.drawString(50, y, f"Notas: {notes}")
    c.save()


def run_eod(store, d: date, user, notes: str = "", force: bool = False):
    export_dir = Path(settings.EOD_EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)
    base = export_dir / f"eod_{store.code}_{d.isoformat()}"
    pdf_path = base.with_suffix(".pdf")
    csv_path = base.with_suffix(".csv")

    existing = DayClose.objects.filter(store=store, date=d).first()
    if existing and not force:
        return existing, False

    write_pdf(pdf_path, store, d, notes=notes)
    write_csv(csv_path, store, d)

    if existing and force:
        existing.export_pdf_path = str(pdf_path)
        existing.export_csv_path = str(csv_path)
        existing.notes = notes
        existing.save()
        return existing, True

    close = DayClose.objects.create(
        store=store,
        date=d,
        export_pdf_path=str(pdf_path),
        export_csv_path=str(csv_path),
        notes=notes,
        created_by=user,
    )
    return close, True
