from decimal import Decimal

import pytest

from core.models import Store
from warehouse.inventory import (
    aggregate_stock_quantity,
    stock_rows,
    suggested_restock_multi,
)
from warehouse.models import Product, StockLevel


@pytest.mark.django_db
class TestInventoryMultiStore:
    def test_stock_rows_accepts_store_instance(self, store_ops_setup):
        rows = stock_rows(store_ops_setup["store"])
        assert len(rows) == 1

    def test_suggested_zero_when_no_max(self, store_ops_setup):
        product = store_ops_setup["product"]
        assert (
            suggested_restock_multi(product, [store_ops_setup["store"].pk])
            == Decimal(0)
        )

    def test_aggregate_and_suggested(self, store_ops_setup):
        data = store_ops_setup
        other = Store.objects.create(name="Sur", code="sur")
        product = data["product"]
        StockLevel.objects.create(
            store=other, product=product, quantity=Decimal("10")
        )
        ids = [data["store"].pk, other.pk]
        assert aggregate_stock_quantity(product, ids) == Decimal("110")
        product.stock_max = Decimal("200")
        product.save()
        assert suggested_restock_multi(product, ids) == Decimal("90")

    def test_stock_rows_low_and_suggested_multi(self, store_ops_setup):
        data = store_ops_setup
        product = data["product"]
        product.reorder_min = Decimal("50")
        product.stock_max = Decimal("200")
        product.save()
        data["stock"].quantity = Decimal("5")
        data["stock"].save()
        ids = [data["store"].pk]
        low = stock_rows(ids, low_only=True)
        assert len(low) == 1
        suggested = stock_rows(ids, suggested_only=True)
        assert len(suggested) == 1

    def test_stock_rows_multi_store_list(self, store_ops_setup):
        data = store_ops_setup
        other = Store.objects.create(name="Norte", code="norte")
        StockLevel.objects.create(
            store=other, product=data["product"], quantity=Decimal("7")
        )
        ids = [data["store"].pk, other.pk]
        rows = stock_rows(ids)
        assert len(rows) == 1
        assert rows[0]["quantity"] == Decimal("107")

    def test_stock_rows_low_multi(self, store_ops_setup):
        data = store_ops_setup
        other = Store.objects.create(name="Norte", code="norte2")
        product = data["product"]
        product.reorder_min = Decimal("50")
        product.save()
        StockLevel.objects.create(
            store=other, product=product, quantity=Decimal("5")
        )
        data["stock"].quantity = Decimal("10")
        data["stock"].save()
        rows = stock_rows([data["store"].pk, other.pk], low_only=True)
        assert len(rows) == 1
        assert rows[0]["quantity"] == Decimal("15")

    def test_stock_rows_suggested_multi(self, store_ops_setup):
        data = store_ops_setup
        other = Store.objects.create(name="Este", code="este")
        product = data["product"]
        product.stock_max = Decimal("200")
        product.save()
        data["stock"].quantity = Decimal("40")
        data["stock"].save()
        StockLevel.objects.create(
            store=other, product=product, quantity=Decimal("40")
        )
        rows = stock_rows([data["store"].pk, other.pk], suggested_only=True)
        assert len(rows) == 1
        assert rows[0]["suggested"] > 0
