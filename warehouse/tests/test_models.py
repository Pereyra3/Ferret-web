from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import Store
from sales.models import DayClose, Sale, SaleLine
from warehouse.models import (
    Product,
    Purchase,
    PurchaseLine,
    StockLevel,
    StockMovement,
    Supplier,
    SupplierPayment,
)


@pytest.mark.django_db
class TestModelStrAndHelpers:
    def test_str_methods(self, store_ops_setup, create_confirmed_sale, create_purchase):
        data = store_ops_setup
        assert str(data["store"])
        assert str(data["supplier"])
        assert str(data["product"])
        assert str(data["stock"])

        sale = create_confirmed_sale()
        assert str(sale)
        line = sale.lines.first()
        assert line.line_total == Decimal("30")

        purchase = create_purchase()
        assert str(purchase)
        assert purchase.total() == Decimal("50")

        pay = SupplierPayment.objects.create(
            store=data["store"],
            supplier=data["supplier"],
            user=data["user"],
            amount=Decimal("1"),
        )
        assert str(pay)

        movement = StockMovement.objects.create(
            store=data["store"],
            product=data["product"],
            quantity_delta=Decimal("1"),
            reason=StockMovement.Reason.ADJUSTMENT,
            reference="t",
            created_by=data["user"],
        )
        assert str(movement)

        close = DayClose.objects.create(store=data["store"], date=timezone.localdate())
        assert str(close)

    def test_supplier_totals_without_store_filter(
        self, store_ops_setup, create_purchase
    ):
        supplier = store_ops_setup["supplier"]
        create_purchase()
        assert supplier.purchases_total() >= Decimal("0")
        assert supplier.payments_total() >= Decimal("0")
        assert supplier.balance() >= Decimal("0")


@pytest.mark.django_db
class TestProductModel:
    def test_stock_quantity_without_level_returns_zero(self, create_store, create_product):
        store = create_store()
        product = create_product()
        assert product.stock_quantity(store) == 0

    def test_suggested_restock_to_max(self, store_ops_setup):
        data = store_ops_setup
        product = data["product"]
        store = data["store"]
        product.stock_max = Decimal("150")
        product.save()
        data["stock"].quantity = Decimal("100")
        data["stock"].save()

        assert product.suggested_restock(store) == Decimal("50")

    def test_sale_is_draft(self, create_confirmed_sale):
        sale = create_confirmed_sale()
        assert sale.is_draft is False
        sale.status = Sale.Status.DRAFT
        assert sale.is_draft is True

    def test_suggested_restock_zero_when_at_max_or_unset(self, store_ops_setup):
        data = store_ops_setup
        product = data["product"]
        store = data["store"]
        assert product.suggested_restock(store) == Decimal(0)

        product.stock_max = Decimal("50")
        product.save()
        data["stock"].quantity = Decimal("50")
        data["stock"].save()
        assert product.suggested_restock(store) == Decimal(0)


@pytest.mark.django_db
class TestSupplierModel:
    def test_supplier_balance(self, store_ops_setup, create_purchase, create_supplier_payment):
        supplier = store_ops_setup["supplier"]
        store = store_ops_setup["store"]
        create_purchase(quantity=Decimal("4"), unit_cost=Decimal("10"))
        create_supplier_payment(amount=Decimal("25"))
        assert supplier.balance(store) == Decimal("15")


@pytest.mark.django_db
class TestStockLevelModel:
    def test_unique_store_product(self, store_ops_setup, create_product):
        from django.db import IntegrityError

        store = store_ops_setup["store"]
        other = create_product(sku="SKU-002")
        StockLevel.objects.create(store=store, product=other, quantity=Decimal("1"))
        with pytest.raises(IntegrityError):
            StockLevel.objects.create(store=store, product=other, quantity=Decimal("2"))
