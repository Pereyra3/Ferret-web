import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from core.roles import GROUP_CAJERO, GROUP_ENCARGADO, GROUP_GERENTE


@pytest.fixture
def role_groups(db):
    call_command("setup_roles")
    return {
        "cajero": Group.objects.get(name=GROUP_CAJERO),
        "encargado": Group.objects.get(name=GROUP_ENCARGADO),
        "gerente": Group.objects.get(name=GROUP_GERENTE),
    }


@pytest.fixture
def client_as(client, django_user_model, store_ops_setup, role_groups):
    def _login(group_name: str):
        user = django_user_model.objects.create_user(
            username=f"user_{group_name}",
            password="pass",
        )
        user.groups.set([role_groups[group_name]])
        user.is_staff = group_name == GROUP_GERENTE
        user.save()
        store_ops_setup["store"].assigned_users.add(user)
        client.login(username=user.username, password="pass")
        return client

    return _login


@pytest.mark.django_db
class TestRolePermissions:
    def test_cajero_can_sale_not_stock_adjust(self, client_as):
        c = client_as("cajero")
        assert c.get(reverse("sale_create")).status_code == 200
        assert c.get(reverse("stock_adjust")).status_code == 403

    def test_encargado_can_stock_not_eod(self, client_as):
        c = client_as("encargado")
        assert c.get(reverse("stock_adjust")).status_code == 200
        assert c.get(reverse("eod")).status_code == 403

    def test_gerente_can_eod_and_store_select(self, client_as, store_ops_setup):
        from django.contrib.auth import get_user_model

        from core.models import Store

        c = client_as("gerente")
        assert c.get(reverse("eod")).status_code == 200
        user = get_user_model().objects.get(username="user_gerente")
        store_ops_setup["store"].assigned_users.add(user)
        Store.objects.create(name="Sucursal 2", code="s2", is_default=False).assigned_users.add(
            user
        )
        assert c.get(reverse("store_select")).status_code == 200

    def test_cajero_single_store_redirects_store_select(self, client_as, store_ops_setup):
        from django.contrib.auth import get_user_model

        c = client_as("cajero")
        user = get_user_model().objects.get(username="user_cajero")
        store_ops_setup["store"].assigned_users.add(user)
        r = c.get(reverse("store_select"))
        assert r.status_code == 302
        assert reverse("home") in r.url

    def test_encargado_cannot_dashboard(self, client_as):
        c = client_as("encargado")
        assert c.get(reverse("dashboard")).status_code == 200

    def test_cajero_cannot_dashboard(self, client_as):
        c = client_as("cajero")
        assert c.get(reverse("dashboard")).status_code == 403
