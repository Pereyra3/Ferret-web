"""Tests for core, warehouse, and sales views."""

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

from core.models import Store
from core.utils import get_default_store, parse_date_range, range_bounds
from core.views.profit import (
    bucket_totals,
    confirmed_sale_lines,
    format_bucket_label,
    profit_series,
    profit_totals,
    trunc_for_granularity,
)
from sales.models import Sale
from warehouse.models import Product, StockLevel


def _sale_line_payload(product, sale=None, **extra):
    """POST body for sale form (lines + notes only)."""
    base = {"notes": ""}
    if sale is not None:
        lines = list(sale.lines.select_related("product"))
        base["lines-TOTAL_FORMS"] = str(len(lines))
        base["lines-INITIAL_FORMS"] = str(len(lines))
        base["lines-MIN_NUM_FORMS"] = "0"
        base["lines-MAX_NUM_FORMS"] = "1000"
        for i, line in enumerate(lines):
            base[f"lines-{i}-id"] = line.pk
            base[f"lines-{i}-product"] = line.product_id
            base[f"lines-{i}-quantity"] = str(line.quantity)
            base[f"lines-{i}-unit_price"] = str(line.unit_price)
            base[f"lines-{i}-DELETE"] = ""
    else:
        base.update(
            {
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-product": product.pk,
                "lines-0-quantity": "2",
                "lines-0-unit_price": "10.00",
                "lines-0-DELETE": "",
            }
        )
    base.update(extra)
    return base


def _checkout_payload(**extra):
    return {
        "payment_method": Sale.PaymentMethod.CASH,
        "amount_tendered": "100.00",
        **extra,
    }


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


class TestSaleFormHelpers:
    def test_total_from_formset_skips_deleted_and_empty(self):
        from sales.sale_workflow import total_from_formset as _total_from_formset

        class _Form:
            def __init__(self, data):
                self.cleaned_data = data

        formset = type(
            "FS",
            (),
            {
                "forms": [
                    _Form({"DELETE": True, "product": 1, "quantity": 99, "unit_price": 99}),
                    _Form({"product": 1, "quantity": 2, "unit_price": 10}),
                    _Form({"DELETE": False, "product": None}),
                ]
            },
        )()
        assert _total_from_formset(formset) == Decimal("20")


@pytest.mark.django_db
class TestViewHelpers:
    """Unit tests for private helpers in views.py."""

    def test_parse_range_invalid_and_swapped(self):
        factory = RequestFactory()
        today = timezone.localdate()
        req = factory.get("/", {"from": "bad", "to": "also-bad"})
        d_from, d_to = parse_date_range(req)
        assert d_from == today - timedelta(days=30)
        assert d_to == today

        req2 = factory.get("/", {"from": "2099-01-01", "to": "2020-01-01"})
        d_from2, d_to2 = parse_date_range(req2)
        assert d_from2 <= d_to2

    def test_format_bucket_label_variants(self):
        assert format_bucket_label(None, "day") == ""
        aware = timezone.make_aware(datetime(2026, 3, 15, 12, 0))
        assert format_bucket_label(aware, "year") == "2026"
        assert format_bucket_label(aware, "month") == "2026-03"
        assert format_bucket_label(aware, "day") == "2026-03-15"

        class OddBucket:
            def __str__(self):
                return "odd-label"

        with patch("core.views.profit.timezone.is_aware", return_value=False):
            assert format_bucket_label(OddBucket(), "day") == "odd-label"

    def test_trunc_for_granularity(self):
        assert trunc_for_granularity("month").__class__.__name__ == "TruncMonth"
        assert trunc_for_granularity("year").__class__.__name__ == "TruncYear"
        assert trunc_for_granularity("day").__class__.__name__ == "TruncDay"

    def test_profit_totals_and_series(
        self,
        store_ops_setup,
        create_confirmed_sale,
        create_purchase,
        create_supplier_payment,
    ):
        data = store_ops_setup
        now = timezone.now()
        start, end = range_bounds(
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

        totals = profit_totals([data["store"].pk], start, end)
        assert totals["sales_total"] == Decimal("200")
        assert totals["net_cash"] == Decimal("160")

        series = profit_series([data["store"].pk], start, end, "day")
        assert series["labels"]
        assert series["profit_operating"]

        from core.views.profit import line_total_expr

        qs = confirmed_sale_lines([data["store"].pk], start, end)
        buckets = bucket_totals(qs, "sale__created_at", line_total_expr(), "month")
        assert isinstance(buckets, dict)

    def test_store_missing_on_request(self, create_user):
        factory = RequestFactory()
        request = factory.get("/")
        request.user = create_user()
        with pytest.raises(ValueError, match="No default store"):
            get_default_store(request)

    def test_store_none_in_database(self, create_user, create_store):
        create_store()
        Store.objects.all().delete()
        factory = RequestFactory()
        request = factory.get("/")
        request.user = create_user()
        request.default_store = SimpleLazyObject(lambda: None)
        with pytest.raises(ValueError, match="No store in database"):
            get_default_store(request)


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
                "department": "Herramientas",
                "location": "Estante 3",
                "list_price": "9.99",
                "reorder_min": "1",
                "stock_max": "200",
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
                "stock_max": "0",
            },
        )
        assert response.status_code == 302
        p.refresh_from_db()
        assert p.name == "Editado"

    def test_stock_list_aggregates_multiple_stores(
        self, authenticated_client, store_ops_setup
    ):
        from decimal import Decimal

        from core.models import Store
        from warehouse.models import StockLevel

        data = store_ops_setup
        other = Store.objects.create(name="Sucursal Sur", code="sur")
        other.assigned_users.add(data["user"])
        StockLevel.objects.create(
            store=other, product=data["product"], quantity=Decimal("25")
        )
        r = authenticated_client.get(reverse("stock_list"))
        assert r.status_code == 200
        assert b"125" in r.content
        authenticated_client.post(
            reverse("store_select"), {"stores": [str(other.pk)]}
        )
        r2 = authenticated_client.get(reverse("stock_list"))
        assert b"25" in r2.content

    def test_product_list_low_stock_single_store(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        data["product"].reorder_min = Decimal("200")
        data["product"].save()
        assert authenticated_client.get(reverse("product_list")).status_code == 200

    def test_product_list_low_stock_multi_store(
        self, authenticated_client, store_ops_setup
    ):
        from core.models import Store

        data = store_ops_setup
        otra = Store.objects.create(name="Otra", code="otra", is_default=False)
        otra.assigned_users.add(data["user"])
        data["product"].reorder_min = Decimal("200")
        data["product"].save()
        assert authenticated_client.get(reverse("product_list")).status_code == 200

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
                "action": "checkout",
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

    def test_sale_create_invalid_formset_rerenders(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        payload = _sale_line_payload(data["product"], action="draft")
        payload["lines-0-quantity"] = ""
        response = authenticated_client.post(reverse("sale_create"), payload)
        assert response.status_code == 200

    def test_sale_edit_get_and_invalid_post(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="draft"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        assert authenticated_client.get(reverse("sale_edit", args=[sale.pk])).status_code == 200
        payload = _sale_line_payload(data["product"], sale=sale, action="draft")
        payload["lines-0-quantity"] = ""
        assert authenticated_client.post(reverse("sale_edit", args=[sale.pk]), payload).status_code == 200

    def test_sale_edit_checkout_redirect(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="draft"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        response = authenticated_client.post(
            reverse("sale_edit", args=[sale.pk]),
            _sale_line_payload(data["product"], sale=sale, action="checkout"),
        )
        assert response.status_code == 302
        assert reverse("sale_checkout", kwargs={"pk": sale.pk}) in response.url

    def test_sale_checkout_flow_cash_and_print(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        r1 = authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="checkout"),
        )
        assert r1.status_code == 302
        assert "/cobrar/" in r1.url
        sale = Sale.objects.get(status=Sale.Status.DRAFT)

        checkout_get = authenticated_client.get(reverse("sale_checkout", args=[sale.pk]))
        assert checkout_get.status_code == 200
        assert checkout_get.context["total"] == Decimal("20")

        r2 = authenticated_client.post(
            reverse("sale_checkout", args=[sale.pk]),
            _checkout_payload(amount_tendered="50.00"),
        )
        assert r2.status_code == 302
        assert "auto=1" in r2.url
        assert reverse("print_sale", kwargs={"pk": sale.pk}) in r2.url

        sale.refresh_from_db()
        assert sale.status == Sale.Status.CONFIRMED
        assert sale.change_amount == Decimal("30.00")
        data["stock"].refresh_from_db()
        assert data["stock"].quantity == Decimal("98")

        ticket = authenticated_client.get(reverse("print_sale", args=[sale.pk]))
        body = ticket.content.decode()
        assert "Ticket #" in body
        assert "Cajero:" in body
        assert data["store"].name in body
        assert data["store"].location in body
        assert "Tel:" in body
        assert "RFC:" in body

    def test_sale_create_draft_then_checkout(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        response = authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="draft"),
        )
        assert response.status_code == 302
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        data["stock"].refresh_from_db()
        assert data["stock"].quantity == Decimal("100")

        authenticated_client.post(
            reverse("sale_checkout", args=[sale.pk]),
            _checkout_payload(amount_tendered="25.00"),
        )
        sale.refresh_from_db()
        assert sale.status == Sale.Status.CONFIRMED

    def test_sale_checkout_card_no_change(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="checkout"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        authenticated_client.post(
            reverse("sale_checkout", args=[sale.pk]),
            {"payment_method": Sale.PaymentMethod.CARD},
        )
        sale.refresh_from_db()
        assert sale.status == Sale.Status.CONFIRMED
        assert sale.change_amount is None

    def test_sale_checkout_insufficient_cash(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="checkout"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        response = authenticated_client.post(
            reverse("sale_checkout", args=[sale.pk]),
            _checkout_payload(amount_tendered="5.00"),
        )
        assert response.status_code == 200
        sale.refresh_from_db()
        assert sale.status == Sale.Status.DRAFT

    def test_sale_checkout_missing_tendered(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="checkout"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        response = authenticated_client.post(
            reverse("sale_checkout", args=[sale.pk]),
            {"payment_method": Sale.PaymentMethod.CASH, "amount_tendered": ""},
        )
        assert response.status_code == 200

    def test_sale_edit_not_allowed_when_confirmed(
        self, authenticated_client, create_confirmed_sale
    ):
        sale = create_confirmed_sale()
        assert authenticated_client.get(reverse("sale_edit", args=[sale.pk])).status_code == 404
        assert authenticated_client.get(reverse("sale_checkout", args=[sale.pk])).status_code == 404

    def test_sale_edit_save_draft_redirects_back(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="draft"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        response = authenticated_client.post(
            reverse("sale_edit", args=[sale.pk]),
            _sale_line_payload(data["product"], sale=sale, action="draft"),
        )
        assert response.status_code == 302
        assert f"/ventas/{sale.pk}/editar/" in response.url

    def test_sale_checkout_invalid_form(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="checkout"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        response = authenticated_client.post(
            reverse("sale_checkout", args=[sale.pk]),
            {"payment_method": "invalid"},
        )
        assert response.status_code == 200

    def test_print_sale_requires_confirmed(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        authenticated_client.post(
            reverse("sale_create"),
            _sale_line_payload(data["product"], action="checkout"),
        )
        sale = Sale.objects.get(status=Sale.Status.DRAFT)
        assert authenticated_client.get(reverse("print_sale", args=[sale.pk])).status_code == 404

    def test_purchase_create_get_post(self, authenticated_client, store_ops_setup):
        data = store_ops_setup
        assert authenticated_client.get(reverse("purchase_create")).status_code == 200
        response = authenticated_client.post(
            reverse("purchase_create"),
            _purchase_formset_data(data["product"], data["supplier"]),
        )
        assert response.status_code == 302

    def test_purchase_create_invalid_rerenders(self, authenticated_client, store_ops_setup):
        data = store_ops_setup
        response = authenticated_client.post(
            reverse("purchase_create"),
            {"supplier": "", "reference": "", "lines-TOTAL_FORMS": "0"},
        )
        assert response.status_code == 200

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

    def test_stock_list_suggested_to_max(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        data["product"].stock_max = Decimal("100")
        data["product"].save()
        data["stock"].quantity = Decimal("40")
        data["stock"].save()

        response = authenticated_client.get(
            reverse("stock_list"), {"suggested": "1"}
        )
        assert response.status_code == 200
        assert response.context["suggested_only"] is True
        assert len(response.context["rows"]) == 1
        assert response.context["rows"][0]["suggested"] == Decimal("60")
        assert response.context["suggested_total"] == Decimal("60")

    def test_stock_list_department_and_location_filters(
        self, authenticated_client, store_ops_setup, create_product
    ):
        data = store_ops_setup
        data["product"].department = "Plomería"
        data["product"].location = "Pasillo A"
        data["product"].save()
        other = create_product(sku="SKU-002", name="Otro", department="Electricidad")
        StockLevel.objects.create(
            store=data["store"],
            product=other,
            quantity=Decimal("5"),
        )

        by_dept = authenticated_client.get(
            reverse("stock_list"), {"department": "Plomería"}
        )
        assert len(by_dept.context["rows"]) == 1
        assert by_dept.context["rows"][0]["product"].sku == data["product"].sku

        by_loc = authenticated_client.get(
            reverse("stock_list"), {"location": "Pasillo A"}
        )
        assert len(by_loc.context["rows"]) == 1

        data["product"].stock_max = Decimal("100")
        data["product"].save()
        data["stock"].quantity = Decimal("10")
        data["stock"].save()
        suggested = authenticated_client.get(
            reverse("stock_list"),
            {"suggested": "1", "department": "Plomería"},
        )
        assert suggested.context["suggested_only"] is True
        assert len(suggested.context["rows"]) == 1

        data["product"].reorder_min = Decimal("200")
        data["product"].save()
        data["stock"].quantity = Decimal("10")
        data["stock"].save()
        low = authenticated_client.get(
            reverse("stock_list"),
            {"low": "1", "location": "Pasillo A"},
        )
        assert low.context["low_only"] is True
        assert len(low.context["rows"]) == 1
        assert low.context["rows"][0]["product"].location == "Pasillo A"

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

    def test_print_stock_suggested_ticket(
        self, authenticated_client, store_ops_setup
    ):
        data = store_ops_setup
        data["product"].stock_max = Decimal("80")
        data["product"].save()
        data["stock"].quantity = Decimal("50")
        data["stock"].save()

        response = authenticated_client.get(reverse("print_stock_suggested"))
        assert response.status_code == 200
        assert "INVENTARIO SUGERIDO" in response.content.decode()
        assert "30" in response.content.decode()

    def test_print_eod_sales_ticket(
        self, authenticated_client, create_confirmed_sale
    ):
        create_confirmed_sale(quantity=Decimal("1"), unit_price=Decimal("25"))
        today = timezone.localdate().isoformat()
        response = authenticated_client.get(
            reverse("print_eod_sales"), {"date": today}
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "CIERRE DE VENTAS" in content
        assert "25" in content

    def test_print_eod_sales_invalid_date_defaults_today(
        self, authenticated_client
    ):
        response = authenticated_client.get(
            reverse("print_eod_sales"), {"date": "invalid"}
        )
        assert response.status_code == 200

    def test_print_views_require_login(self, client):
        assert client.get(reverse("print_stock_suggested")).status_code == 302
        assert client.get(reverse("print_eod_sales")).status_code == 302
