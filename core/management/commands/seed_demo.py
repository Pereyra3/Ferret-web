"""
Wipe operational data and load a full demo dataset (products, stock, purchases, sales, EOD).
Preserves Django auth users unless --flush-users is passed.
"""
from datetime import timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Store
from sales.models import DayClose, Sale, SaleLine
from sales.services.eod import run_eod
from warehouse.models import (
    Product,
    Purchase,
    PurchaseLine,
    StockLevel,
    StockMovement,
    Supplier,
    SupplierPayment,
)
from warehouse.services.stock import apply_purchase, apply_sale


PRODUCTS = [
    # sku, name, category, department, location, list_price, reorder_min, stock_max
    ("TUB-PVC-32", "Tubo PVC 32 mm x 3 m", "Plomería", "Plomería", "Pasillo A-1", "45.00", "10", "80"),
    ("CODO-PVC-32", "Codo PVC 32 mm 90°", "Plomería", "Plomería", "Pasillo A-1", "8.50", "20", "120"),
    ("LLAV-ESFERA-12", "Llave de esfera 1/2\"", "Plomería", "Plomería", "Pasillo A-2", "125.00", "5", "40"),
    ("CEMENT-PVC-250", "Cemento PVC 250 ml", "Plomería", "Plomería", "Pasillo A-2", "35.00", "15", "60"),
    ("MANG-FLEX-50", "Manguera flexible 50 cm", "Plomería", "Plomería", "Pasillo A-3", "28.00", "12", "50"),
    ("TALADRO-550W", "Taladro percutor 550 W", "Herramientas", "Herramientas", "Pasillo B-4", "890.00", "3", "15"),
    ("JGO-DESARM-6", "Juego desarmadores 6 pzas", "Herramientas", "Herramientas", "Pasillo B-5", "145.00", "8", "35"),
    ("MARTILLO-16", "Martillo uña 16 oz", "Herramientas", "Herramientas", "Pasillo B-5", "210.00", "6", "25"),
    ("CINTA-METR-5", "Cinta métrica 5 m", "Herramientas", "Herramientas", "Pasillo B-6", "65.00", "10", "45"),
    ("LLAVE-STIL-10", "Llave stilson 10\"", "Herramientas", "Herramientas", "Pasillo B-6", "320.00", "4", "20"),
    ("PINT-LATEX-BCO-4", "Pintura látex blanco 4 L", "Pintura", "Pintura", "Pasillo C-7", "285.00", "8", "40"),
    ("PINT-LATEX-GRIS-1", "Pintura látex gris 1 L", "Pintura", "Pintura", "Pasillo C-7", "95.00", "12", "55"),
    ("RODILLO-9", "Rodillo 9\" felpa", "Pintura", "Pintura", "Pasillo C-8", "42.00", "15", "70"),
    ("BROCHA-4", "Brocha 4\" cerda natural", "Pintura", "Pintura", "Pasillo C-8", "38.00", "15", "70"),
    ("THINNER-1L", "Thinner universal 1 L", "Pintura", "Pintura", "Pasillo C-9", "48.00", "10", "50"),
    ("CABLE-THW-12", "Cable THW calibre 12 (metro)", "Electricidad", "Electricidad", "Pasillo D-10", "18.00", "50", "200"),
    ("CABLE-THW-10", "Cable THW calibre 10 (metro)", "Electricidad", "Electricidad", "Pasillo D-10", "24.00", "40", "150"),
    ("CONTACTO-SIMP", "Contacto sencillo blanco", "Electricidad", "Electricidad", "Pasillo D-11", "22.00", "25", "100"),
    ("APAGADOR-SIMP", "Apagador sencillo blanco", "Electricidad", "Electricidad", "Pasillo D-11", "28.00", "25", "100"),
    ("FOCO-LED-9W", "Foco LED 9 W luz cálida", "Electricidad", "Electricidad", "Pasillo D-12", "35.00", "30", "120"),
    ("CLAVO-2P-1KG", "Clavos 2\" caja 1 kg", "Fijación", "Herramientas", "Pasillo B-7", "55.00", "10", "40"),
    ("TORN-MAD-8x1", "Tornillo madera 8x1\" (100 pzas)", "Fijación", "Herramientas", "Pasillo B-7", "72.00", "12", "50"),
    ("SILICON-TRANSP", "Silicón transparente 280 ml", "Selladores", "Plomería", "Pasillo A-4", "52.00", "10", "45"),
    ("CANDADO-40", "Candado latón 40 mm", "Seguridad", "Herramientas", "Pasillo B-8", "118.00", "6", "30"),
    ("BROCA-8MM", "Broca para concreto 8 mm", "Herramientas", "Herramientas", "Pasillo B-4", "28.00", "20", "80"),
    ("LLAVE-ALLEN-JGO", "Juego llaves Allen métricas", "Herramientas", "Herramientas", "Pasillo B-5", "95.00", "8", "35"),
    ("TINACO-1100", "Tinaco rotoplas 1100 L", "Plomería", "Plomería", "Patio trasero P-1", "2850.00", "1", "5"),
    ("WC-MONOBLOQ", "WC monoblock económico", "Plomería", "Plomería", "Patio trasero P-2", "1650.00", "2", "8"),
    ("LAVABO-PED", "Lavabo pedestal blanco", "Plomería", "Plomería", "Patio trasero P-2", "980.00", "2", "8"),
    ("CEMENTO-50KG", "Cemento gris 50 kg", "Construcción", "Construcción", "Patio exterior P-3", "185.00", "20", "100"),
]

SUPPLIERS = [
    ("Distribuidora Norte SA", Decimal("1500.00")),
    ("Plásticos y Tuberías del Bajío", Decimal("0")),
    ("Eléctricos Martínez", Decimal("800.00")),
    ("Pinturas y Acabados López", Decimal("250.00")),
]


class Command(BaseCommand):
    help = "Delete operational data and seed a full demo database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-users",
            action="store_true",
            help="Also delete all users and recreate demo/demo login.",
        )
        parser.add_argument(
            "--no-eod",
            action="store_true",
            help="Skip generating EOD PDF/CSV exports for past days.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            self._clear_data(flush_users=options["flush_users"])
            store, user = self._ensure_store_and_user(flush_users=options["flush_users"])
            suppliers = self._create_suppliers()
            products = self._create_products()
            self._create_stock(store, products)
            self._create_purchases(store, user, suppliers, products)
            self._create_payments(store, user, suppliers)
            self._create_sales(store, user, products)
            if not options["no_eod"]:
                self._create_day_closes(store, user)

        self.stdout.write(self.style.SUCCESS("Base de datos demo cargada correctamente."))
        self.stdout.write(
            f"Productos: {Product.objects.count()} | Proveedores: {Supplier.objects.count()} | "
            f"Compras: {Purchase.objects.count()} | Pagos: {SupplierPayment.objects.count()}"
        )
        self.stdout.write(
            f"Ventas confirmadas: {Sale.objects.filter(status=Sale.Status.CONFIRMED).count()} | "
            f"Borradores: {Sale.objects.filter(status=Sale.Status.DRAFT).count()} | "
            f"Cierres día: {DayClose.objects.count()}"
        )
        self.stdout.write(
            "Si no tiene usuario, ejecute: python manage.py setup_defaults (demo / demo)"
        )

    def _clear_data(self, *, flush_users: bool):
        self.stdout.write("Eliminando datos operativos…")
        DayClose.objects.all().delete()
        SaleLine.objects.all().delete()
        Sale.objects.all().delete()
        StockMovement.objects.all().delete()
        StockLevel.objects.all().delete()
        PurchaseLine.objects.all().delete()
        Purchase.objects.all().delete()
        SupplierPayment.objects.all().delete()
        Product.objects.all().delete()
        Supplier.objects.all().delete()
        Store.objects.all().delete()

        if flush_users:
            get_user_model().objects.all().delete()
            self.stdout.write("Usuarios eliminados.")

    def _ensure_store_and_user(self, *, flush_users: bool):
        store = Store.objects.create(
            name="Ferretería Central",
            code="principal",
            is_default=True,
            location="Av. Insurgentes Sur 123, Col. Del Valle, CDMX",
            phone="55 5555 1234",
            rfc="FER123456ABC",
        )
        User = get_user_model()
        from core.roles import GROUP_GERENTE, setup_role_groups
        from django.contrib.auth.models import Group

        setup_role_groups()
        gerente_group = Group.objects.get(name=GROUP_GERENTE)

        if flush_users or not User.objects.exists():
            user = User.objects.create_user(username="demo", password="demo", is_staff=True)
            self.stdout.write(self.style.SUCCESS("Usuario: demo / demo"))
        else:
            user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        demo, created = User.objects.get_or_create(username="demo", defaults={"is_staff": True})
        demo.groups.set([gerente_group])
        demo.is_staff = True
        if created or not demo.has_usable_password():
            demo.set_password("demo")
        demo.save()
        self.stdout.write(f"Ventas atribuidas a: {user.username} | Acceso caja: demo / demo")

        return store, user

    def _create_suppliers(self):
        out = []
        for name, opening in SUPPLIERS:
            out.append(Supplier.objects.create(name=name, opening_balance=opening))
        return out

    def _create_products(self):
        out = []
        for row in PRODUCTS:
            sku, name, cat, dept, loc, price, reorder, smax = row
            out.append(
                Product.objects.create(
                    sku=sku,
                    name=name,
                    category=cat,
                    department=dept,
                    location=loc,
                    list_price=Decimal(price),
                    reorder_min=Decimal(reorder),
                    stock_max=Decimal(smax),
                )
            )
        return out

    def _create_stock(self, store, products):
        """Initial on-hand quantities: mix of normal, low, and below-max for suggestions."""
        rng = random.Random(42)
        for p in products:
            cap = Decimal(p.stock_max or 0)
            if cap > 0:
                # ~40% below max (suggested restock), ~15% low vs reorder_min
                roll = rng.random()
                if roll < 0.15 and p.reorder_min > 0:
                    qty = max(Decimal("0"), p.reorder_min - Decimal("2"))
                elif roll < 0.55:
                    qty = (cap * Decimal(rng.uniform(0.35, 0.85))).quantize(Decimal("0.001"))
                else:
                    qty = cap
            else:
                qty = Decimal(rng.randint(5, 80))
            StockLevel.objects.create(store=store, product=p, quantity=qty)

    def _create_purchases(self, store, user, suppliers, products):
        rng = random.Random(7)
        now = timezone.now()
        for i in range(12):
            supplier = suppliers[i % len(suppliers)]
            purchase = Purchase.objects.create(
                store=store,
                supplier=supplier,
                user=user,
                reference=f"FAC-2026-{1000 + i}",
            )
            Purchase.objects.filter(pk=purchase.pk).update(
                created_at=now - timedelta(days=rng.randint(3, 45), hours=rng.randint(8, 18))
            )
            purchase.refresh_from_db()
            sample = rng.sample(products, k=rng.randint(2, 5))
            for prod in sample:
                cost = (prod.list_price * Decimal("0.62")).quantize(Decimal("0.01"))
                PurchaseLine.objects.create(
                    purchase=purchase,
                    product=prod,
                    quantity=Decimal(rng.randint(5, 40)),
                    unit_cost=cost,
                )
            apply_purchase(purchase, user)

    def _create_payments(self, store, user, suppliers):
        rng = random.Random(99)
        now = timezone.now()
        for i, supplier in enumerate(suppliers):
            for j in range(2):
                pay = SupplierPayment.objects.create(
                    store=store,
                    supplier=supplier,
                    user=user,
                    amount=Decimal(rng.randint(500, 3500)),
                    note="Pago demo",
                    reference=f"TRF-{100 + i}-{j}",
                )
                SupplierPayment.objects.filter(pk=pay.pk).update(
                    created_at=now - timedelta(days=rng.randint(1, 35))
                )

    def _create_sales(self, store, user, products):
        rng = random.Random(123)
        now = timezone.now()
        methods = [
            Sale.PaymentMethod.CASH,
            Sale.PaymentMethod.CARD,
            Sale.PaymentMethod.TRANSFER,
            Sale.PaymentMethod.CASH,
        ]

        for i in range(55):
            method = methods[i % len(methods)]
            sale = Sale.objects.create(
                store=store,
                user=user,
                status=Sale.Status.CONFIRMED,
                payment_method=method,
                notes="" if i % 4 else "Cliente frecuente",
            )
            days_ago = rng.randint(0, 29)
            created = now - timedelta(days=days_ago, hours=rng.randint(9, 20), minutes=rng.randint(0, 59))
            Sale.objects.filter(pk=sale.pk).update(created_at=created)
            sale.refresh_from_db()

            for prod in rng.sample(products, k=rng.randint(1, 4)):
                qty = Decimal(rng.randint(1, 5))
                price = prod.list_price
                if rng.random() < 0.1:
                    price = (price * Decimal("0.95")).quantize(Decimal("0.01"))
                SaleLine.objects.create(
                    sale=sale,
                    product=prod,
                    quantity=qty,
                    unit_price=price,
                )

            total = sale.total()
            if method == Sale.PaymentMethod.CASH:
                tendered = total + Decimal(rng.choice([0, 20, 50, 100]))
                sale.amount_tendered = tendered
                sale.change_amount = tendered - total
            else:
                sale.amount_tendered = None
                sale.change_amount = None
            sale.save(update_fields=["amount_tendered", "change_amount"])
            apply_sale(sale, user)

        # Pending drafts for UI
        for note in ("Pedido mostrador — pendiente cobro", "Cotización cliente García"):
            draft = Sale.objects.create(
                store=store,
                user=user,
                status=Sale.Status.DRAFT,
                notes=note,
            )
            for prod in rng.sample(products, k=2):
                SaleLine.objects.create(
                    sale=draft,
                    product=prod,
                    quantity=Decimal(rng.randint(1, 3)),
                    unit_price=prod.list_price,
                )

    def _create_day_closes(self, store, user):
        today = timezone.localdate()
        for days_ago in range(7, 0, -1):
            d = today - timedelta(days=days_ago)
            run_eod(store, d, user, notes="Cierre demo", force=True)
