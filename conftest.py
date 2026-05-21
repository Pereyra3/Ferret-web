"""Shared pytest fixtures (pattern aligned with tech_tool)."""

from decimal import Decimal

import pytest

from core.models import Store
from sales.models import Sale, SaleLine
from warehouse.models import (
    Product,
    Purchase,
    PurchaseLine,
    StockLevel,
    Supplier,
    SupplierPayment,
)


@pytest.fixture
def create_user(django_user_model):
    def _create_user(username="testuser", password="password"):
        return django_user_model.objects.create_user(
            username=username,
            password=password,
        )

    return _create_user


@pytest.fixture
def create_store():
    def _create_store(**kwargs):
        defaults = {
            "name": "Test Store",
            "code": "principal",
            "is_default": True,
            "location": "Calle Test 1",
            "phone": "55 0000 0000",
            "rfc": "TST010101TST",
        }
        defaults.update(kwargs)
        return Store.objects.create(**defaults)

    return _create_store


@pytest.fixture
def create_supplier():
    def _create_supplier(**kwargs):
        defaults = {
            "name": "Test Supplier",
            "opening_balance": Decimal("0"),
        }
        defaults.update(kwargs)
        return Supplier.objects.create(**defaults)

    return _create_supplier


@pytest.fixture
def create_product():
    def _create_product(**kwargs):
        defaults = {
            "sku": "SKU-001",
            "name": "Test product",
            "list_price": Decimal("10.00"),
            "reorder_min": Decimal("5"),
        }
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    return _create_product


@pytest.fixture
def store_ops_setup(create_user, create_store, create_supplier, create_product, db):
    """Baseline data: user, store, supplier, product, stock (Gerente permissions)."""
    from django.core.management import call_command

    call_command("setup_roles")
    user = create_user()
    from django.contrib.auth.models import Group

    from core.roles import GROUP_GERENTE

    user.groups.set([Group.objects.get(name=GROUP_GERENTE)])
    user.is_staff = True
    user.save()
    store = create_store()
    store.assigned_users.add(user)
    supplier = create_supplier()
    product = create_product()
    stock = StockLevel.objects.create(
        store=store,
        product=product,
        quantity=Decimal("100"),
    )
    return {
        "user": user,
        "store": store,
        "supplier": supplier,
        "product": product,
        "stock": stock,
    }


@pytest.fixture
def authenticated_client(client, store_ops_setup):
    client.login(username="testuser", password="password")
    return client


@pytest.fixture
def create_confirmed_sale(store_ops_setup, create_user):
    def _create_confirmed_sale(
        *,
        quantity=Decimal("2"),
        unit_price=Decimal("15.00"),
        payment_method=Sale.PaymentMethod.CASH,
    ):
        data = store_ops_setup
        sale = Sale.objects.create(
            store=data["store"],
            user=data["user"],
            status=Sale.Status.CONFIRMED,
            payment_method=payment_method,
        )
        SaleLine.objects.create(
            sale=sale,
            product=data["product"],
            quantity=quantity,
            unit_price=unit_price,
        )
        return sale

    return _create_confirmed_sale


@pytest.fixture
def create_purchase(store_ops_setup):
    def _create_purchase(*, quantity=Decimal("10"), unit_cost=Decimal("5.00")):
        data = store_ops_setup
        purchase = Purchase.objects.create(
            store=data["store"],
            supplier=data["supplier"],
            user=data["user"],
        )
        PurchaseLine.objects.create(
            purchase=purchase,
            product=data["product"],
            quantity=quantity,
            unit_cost=unit_cost,
        )
        return purchase

    return _create_purchase


@pytest.fixture
def create_supplier_payment(store_ops_setup):
    def _create_supplier_payment(*, amount=Decimal("50.00")):
        data = store_ops_setup
        return SupplierPayment.objects.create(
            store=data["store"],
            supplier=data["supplier"],
            user=data["user"],
            amount=amount,
        )

    return _create_supplier_payment


@pytest.fixture
def eod_export_dir(settings, tmp_path):
    settings.EOD_EXPORT_DIR = tmp_path
    return tmp_path
