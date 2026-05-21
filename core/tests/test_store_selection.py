import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import reverse

from core.models import Store
from core.store_selection import (
    get_selected_store_ids,
    selection_label,
    set_selected_store_ids,
)


def _request_with_session(user):
    factory = RequestFactory()
    request = factory.get("/")
    request.user = user
    session = SessionStore()
    session.create()
    request.session = session
    return request


def _assign(user, *stores):
    for s in stores:
        s.assigned_users.add(user)


@pytest.mark.django_db
class TestStoreSelection:
    def test_default_single_assigned_store(self, create_user, create_store):
        store = create_store()
        user = create_user()
        _assign(user, store)
        request = _request_with_session(user)
        assert get_selected_store_ids(request) == [store.pk]
        assert store.name in selection_label(request)

    def test_subset_persisted(self, create_user, create_store):
        s1 = create_store()
        s2 = create_store(name="Branch B", code="b", is_default=False)
        user = create_user()
        _assign(user, s1, s2)
        request = _request_with_session(user)
        set_selected_store_ids(request, [s2.pk])
        assert get_selected_store_ids(request) == [s2.pk]
        assert "Branch B" in selection_label(request)

    def test_selection_label_all_and_empty(self, create_user, create_store):
        s1 = create_store()
        s2 = create_store(name="B", code="b2", is_default=False)
        user = create_user()
        _assign(user, s1, s2)
        request = _request_with_session(user)
        assert selection_label(request) == "Todas mis tiendas"
        s1.assigned_users.clear()
        s2.assigned_users.clear()
        assert selection_label(request) == "Sin tienda asignada"

    def test_store_select_get_and_post_all(self, authenticated_client, store_ops_setup):
        Store.objects.create(name="Other", code="other", is_default=False).assigned_users.add(
            store_ops_setup["user"]
        )
        url = reverse("store_select")
        assert authenticated_client.get(url).status_code == 200
        r = authenticated_client.post(url, {"select_all": "on"})
        assert r.status_code == 302
        assert authenticated_client.get(reverse("home")).status_code == 200

    def test_store_select_redirects_single_store_user(
        self, authenticated_client, store_ops_setup
    ):
        assert authenticated_client.get(reverse("store_select")).status_code == 302

    def test_store_select_post_invalid(self, authenticated_client, store_ops_setup):
        Store.objects.create(name="Other", code="other2", is_default=False).assigned_users.add(
            store_ops_setup["user"]
        )
        r = authenticated_client.post(reverse("store_select"), {})
        assert r.status_code == 302
        assert "/tiendas/seleccion/" in r.url
        r2 = authenticated_client.post(reverse("store_select"), {"stores": ["x"]})
        assert r2.status_code == 302

    def test_store_select_post_next(self, authenticated_client, store_ops_setup):
        Store.objects.create(name="Branch", code="branch", is_default=False).assigned_users.add(
            store_ops_setup["user"]
        )
        r = authenticated_client.post(
            reverse("store_select"),
            {"select_all": "on", "next": "/dashboard/"},
        )
        assert r.url.endswith("/dashboard/")

    def test_store_select_filters_sale_list(
        self, authenticated_client, store_ops_setup, create_confirmed_sale
    ):
        data = store_ops_setup
        other = Store.objects.create(name="Sucursal Norte", code="norte")
        other.assigned_users.add(data["user"])
        create_confirmed_sale()
        from sales.models import Sale

        Sale.objects.create(
            store=other,
            user=data["user"],
            status=Sale.Status.CONFIRMED,
        )
        authenticated_client.post(
            reverse("store_select"), {"stores": [str(other.pk)]}
        )
        body = authenticated_client.get(reverse("sale_list")).content.decode()
        assert "Sucursal Norte" in body
        assert "Test Store" not in body

    def test_write_store_hint_on_home_with_two_stores(
        self, authenticated_client, store_ops_setup
    ):
        Store.objects.create(name="Branch", code="branch", is_default=False).assigned_users.add(
            store_ops_setup["user"]
        )
        body = authenticated_client.get(reverse("home")).content.decode()
        assert "se registran en" in body

    def test_mixin_store_scope(
        self, authenticated_client, store_ops_setup, create_confirmed_sale
    ):
        from core.views.views import DashboardView

        Store.objects.create(name="Branch", code="branch", is_default=False).assigned_users.add(
            store_ops_setup["user"]
        )
        create_confirmed_sale()
        request = authenticated_client.get(reverse("dashboard")).wsgi_request
        view = DashboardView()
        view.request = request
        view.setup(request)
        assert view.get_store_ids()
        from sales.models import Sale

        assert view.filter_by_stores(Sale.objects.all()).exists()
        assert view.get_store_filter_kwargs() == {"store__in": view.get_store_ids()}
        stores = view.get_selected_stores()
        assert stores.exists()
        assert view.get_selected_stores() is stores
        assert view.uses_write_store_hint() is True
        authenticated_client.post(
            reverse("store_select"),
            {"stores": [str(store_ops_setup["store"].pk)]},
        )
        request2 = authenticated_client.get(reverse("dashboard")).wsgi_request
        view2 = DashboardView()
        view2.request = request2
        view2.setup(request2)
        assert view2.uses_write_store_hint() is False
