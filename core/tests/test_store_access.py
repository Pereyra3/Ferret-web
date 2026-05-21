import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import reverse

from core.models import Store
from core.store_access import (
    allowed_store_ids,
    ensure_session_store_scope,
    stores_for_user,
    user_can_pick_stores,
    user_has_store_access,
)
from core.store_selection import get_selected_store_ids, selection_label


def _request_with_session(user):
    factory = RequestFactory()
    request = factory.get("/")
    request.user = user
    session = SessionStore()
    session.create()
    request.session = session
    return request


@pytest.mark.django_db
class TestStoreAccess:
    def test_user_sees_only_assigned_stores(self, create_user, create_store):
        user = create_user()
        s1 = create_store(code="a")
        s2 = create_store(name="B", code="b", is_default=False)
        s1.assigned_users.add(user)
        assert list(stores_for_user(user).values_list("code", flat=True)) == ["a"]
        assert user_has_store_access(user)
        assert user_can_pick_stores(user) is False

    def test_superuser_sees_all(self, create_user, create_store):
        user = create_user()
        user.is_superuser = True
        user.save()
        create_store()
        create_store(name="X", code="x", is_default=False)
        assert stores_for_user(user).count() == 2
        assert user_can_pick_stores(user)

    def test_no_assignment_no_access(self, create_user, create_store):
        create_store()
        user = create_user()
        assert not user_has_store_access(user)
        assert allowed_store_ids(user) == []

    def test_single_store_forces_session_scope(self, create_user, create_store):
        user = create_user()
        store = create_store()
        store.assigned_users.add(user)
        request = _request_with_session(user)
        request.session["selected_store_ids"] = [999]
        ensure_session_store_scope(request)
        assert get_selected_store_ids(request) == [store.pk]

    def test_subset_cannot_escape_assignment(self, create_user, create_store):
        user = create_user()
        s1 = create_store(code="a")
        s2 = create_store(name="B", code="b", is_default=False)
        s1.assigned_users.add(user)
        other = create_store(name="Other", code="other", is_default=False)
        request = _request_with_session(user)
        request.session["selected_store_ids"] = [other.pk]
        ensure_session_store_scope(request)
        assert get_selected_store_ids(request) == [s1.pk]

    def test_two_assigned_can_pick(self, create_user, create_store):
        user = create_user()
        s1 = create_store(code="a")
        s2 = create_store(name="B", code="b", is_default=False)
        s1.assigned_users.add(user)
        s2.assigned_users.add(user)
        assert user_can_pick_stores(user)
        request = _request_with_session(user)
        assert selection_label(request) == "Todas mis tiendas"
