"""Tests for store_ops.views (HTTP views and view helpers)."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.messages import get_messages
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import SimpleLazyObject
from rest_framework import status

from store_ops.models import Product, Sale, Store
from store_ops.views import (
    _bucket_totals,
    _confirmed_sale_lines,
    _format_bucket_label,
    _line_total_expr,
    _parse_range,
    _profit_series,
    _profit_totals,
    _range_bounds,
    _store,
    _trunc_for_granularity,
)


def _sale_formset_data(product, **extra):
    base = {
        "payment_method": Sale.PaymentMethod.CASH,
        "notes": "",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-product": product.pk,
        "lines-0-quantity": "2",
        "lines-0-unit_price": "10.00",
        "lines-0-DELETE": "",
    }
    base.update(extra)
    return base


def _purchase_formset_data(product, supplier, **extra):
    base = {
        "supplier": supplier.pk,
        "reference": "INV-1",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "1",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-product": product.pk,
        "lines-0-quantity": "5",
        "lines-0-unit_cost": "3.00",
        "lines-0-DELETE": "",
    }
    base.update(extra)
    return base


@pytest.mark.django_db
class TestViewHelpers:
    """Unit tests for private helpers in views.py."""

    def test_parse_range_invalid_and_swapped(self):
        factory = RequestFactory()
        today = timezone.localdate()
        req = factory.get("/", {"from": "bad", "to": "also-bad"})
        d_from, d_to = _parse_range(req)
        assert d_from == today - timedelta(days=30)
        assert d_to == today

        req2 = factory.get("/", {"from": "2099-01-01", "to": "2020-01-01"})
        d_from2, d_to2 = _parse_range(req2)
        assert d_from2 <= d_to2

    def test_format_bucket_label_variants(self):
        assert _format_bucket_label(None, "day") == ""
        aware = timezone.make_aware(datetime(2026, 3, 15, 12, 0))
        assert _format_bucket_label(aware, "year") == "2026"
        assert _format_bucket_label(aware, "month") == "2026-03"
        assert _format_bucket_label(aware, "day") == "2026-03-15"

        class OddBucket:
            def __str__(self):
                return "odd-label"

        with patch("store_ops.views.timezone.is_aware", return_value=False):
            assert _format_bucket_label(OddBucket(), "day") == "odd-label"

    def test_trunc_for_granularity(self):
        assert _trunc_for_granularity("month").__class__.__name__ == "TruncMonth"
        assert _trunc_for_granularity("year").__class__.__name__ == "TruncYear"
        assert _trunc_for_granularity("day").__class__.__name__ == "TruncDay"

    def test_profit_totals_and_series(
        self,
        store_ops_setup,
        create_confirmed_sale,
        create_purchase,
        create_supplier_payment,
    ):
        data = store_ops_setup
        now = timezone.now()
        start, end = _range_bounds(
            (now - timedelta(days=1)).date(),
            (now + timedelta(days=1)).date(),
        )

        sale = create_confirmed_sale(quantity=Decimal("2"), unit_price=Decimal("100"))
        sale.created_at = now
        sale.save(update_fields=["created_at"])

        purchase = create_purchase(quantity=Decimal("1"), unit_cost=Decimal("30"))
        purchase.created_at = now
        purchase.save(update_fields=["created_at"])

        payment = create_supplier_payment(amount=Decimal("40"))
        payment.created_at = now
        payment.save(update_fields=["created_at"])

        totals = _profit_totals(data["store"], start, end)
        assert totals["sales_total"] == Decimal("200")
        assert totals["net_cash"] == Decimal("160")

        series = _profit_series(data["store"], start, end, "day")
        assert series["labels"]
        assert series["profit_operating"]

        qs = _confirmed_sale_lines(data["store"], start, end)
        buckets = _bucket_totals(qs, "sale__created_at", _line_total_expr(), "month")
        assert isinstance(buckets, dict)

    def test_store_missing_on_request(self, create_user):
        factory = RequestFactory()
        request = factory.get("/")
        request.user = create_user()
        with pytest.raises(ValueError, match="No default store"):
            _store(request)

    def test_store_none_in_database(self, create_user, create_store):
        create_store()
        Store.objects.all().delete()
        factory = RequestFactory()
        request = factory.get("/")
        request.user = create_user()
        request.default_store = SimpleLazyObject(lambda: None)
        with pytest.raises(ValueError, match="No store in database"):
            _store(request)


@pytest.mark.django_db
class TestLoginRequired:
    def test_home_requires_login(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_dashboard_requires_login(self, client):
        assert client.get(reverse("dashboard")).status_code == 302

    def test_api_profit_requires_login(self, client):
        assert client.get(reverse("api_profit_series")).status_code == 302


@pytest.mark.django_db
class TestAuthenticatedViews:
    def test_home_ok(self, authenticated_client):
        assert authenticated_client.get(reverse("home")).status_code == 200

    def test_dashboard_ok_and_invalid_range(self, authenticated_client):
        response = authenticated_client.get(
            reverse("dashboard"),
            {"from": "not-a-date", "to": "also-bad"},
        )
        assert response.status_code == 200
        assert "sales_total" in response.context

    def test_api_profit_series_granularities(
        self, authenticated_client, create_confirmed_sale
    ):
        create_confirmed_sale()
        today = timezone.localdate().isoformat()
        url = reverse("api_profit_series")
        for gran in ("day", "month", "year"):
            response = authenticated_client.get(
                url,
                {"from": today, "to": today, "granularity": gran},
            )
            assert response.status_code == status.HTTP_200_OK
            payload = response.json()
            assert "totals" in payload
            assert payload["granularity"] == gran

    def test_product_list_low_stock_flag(self, authenticated_client, store_ops_setup):
        p = store_ops_setup["product"]
        p.reorder_min = Decimal("1000")
        p.save()
        response = authenticated_client.get(reverse("product_list"))
        assert len(response.context["low_stock"]) == 1

    def test_product_create_get_post(self, authenticated_client):
        assert authenticated_client.get(reverse("product_create")).status_code == 200
        response = authenticated_client.post(
            reverse("product_create"),
            {
                "sku": "NEW-99",
                "name": "Nuevo",
                "category": "Test",
                "list_price": "9.99",
                "reorder_min": "1",
            },
        )
        assert response.status_code == 302
        assert Product.objects.filter(sku="NEW-99").exists()

    def test_product_edit_get_post(self, authenticated_client, store_ops_setup):
        p = store_ops_setup["product"]
        assert authenticated_client.get(reverse("product_edit", args=[p.pk])).status_code == 200
        response = authenticated_client.post(
            reverse("product_edit", args=[p.pk]),
            {
                "sku": p.sku,
                "name": "Editado",
                "category": "",
                "list_price": "11",
                "reorder_min": "0",
            },
        )
        assert response.status_code == 302
        p.refresh_from_db()
        assert p.name == "Editado"

    def test_sale_list(self, authenticated_client, create_confirmed_sale):
        create_confirmed_sale()
        assert authenticated_client.get(reverse("sale_list")).status_code == 200

    def test_sale_create_get_post_and_empty_lines(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        assert authenticated_client.get(reverse("sale_create")).status_code == 200

        response = authenticated_client.post(
            reverse("sale_create"),
            {
                "payment_method": "cash",
                "notes": "",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-0-DELETE": "on",
                "lines-0-product": "",
                "lines-0-quantity": "",
                "lines-0-unit_price": "",
            },
        )
        assert response.status_code == 200
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any("línea" in m.lower() for m in msgs)

        response = authenticated_client.post(
            reverse("sale_create"),
            _sale_formset_data(data["product"]),
        )
        assert response.status_code == 302

    def test_purchase_create_get_post(self, authenticated_client, store_ops_setup):
        data = store_ops_setup
        assert authenticated_client.get(reverse("purchase_create")).status_code == 200
        response = authenticated_client.post(
            reverse("purchase_create"),
            _purchase_formset_data(data["product"], data["supplier"]),
        )
        assert response.status_code == 302

    def test_payment_create_get_post(self, authenticated_client, store_ops_setup):
        data = store_ops_setup
        assert authenticated_client.get(reverse("payment_create")).status_code == 200
        response = authenticated_client.post(
            reverse("payment_create"),
            {
                "supplier": data["supplier"].pk,
                "amount": "25.00",
                "note": "",
                "reference": "",
            },
        )
        assert response.status_code == 302

    def test_stock_list_full_and_low(self, authenticated_client, store_ops_setup):
        data = store_ops_setup
        data["product"].reorder_min = Decimal("200")
        data["product"].save()
        data["stock"].quantity = Decimal("10")
        data["stock"].save()

        full = authenticated_client.get(reverse("stock_list"))
        assert len(full.context["rows"]) == 1
        assert full.context["rows"][0]["is_low"] is True

        low = authenticated_client.get(reverse("stock_list"), {"low": "true"})
        assert low.context["low_only"] is True

    def test_stock_adjust_get_post(self, authenticated_client, store_ops_setup):
        data = store_ops_setup
        assert authenticated_client.get(reverse("stock_adjust")).status_code == 200
        response = authenticated_client.post(
            reverse("stock_adjust"),
            {"product": data["product"].pk, "quantity_delta": "5"},
        )
        assert response.status_code == 302

    def test_eod_get_post_existing_and_force(
        self, authenticated_client, store_ops_setup, create_confirmed_sale, eod_export_dir
    ):
        create_confirmed_sale()
        d = timezone.localdate()
        assert authenticated_client.get(reverse("eod")).status_code == 200

        authenticated_client.post(
            reverse("eod"),
            {"date": d.isoformat(), "notes": "", "force": ""},
        )
        response2 = authenticated_client.post(
            reverse("eod"),
            {"date": d.isoformat(), "notes": "", "force": ""},
        )
        assert response2.status_code == 302

        response3 = authenticated_client.post(
            reverse("eod"),
            {"date": d.isoformat(), "notes": "n", "force": "on"},
        )
        assert response3.status_code == 302
