"""Per-user store access (assigned branches)."""

from django.conf import settings

from core.models import Store


def stores_for_user(user):
    """Stores this user may view and operate on."""
    if not getattr(user, "is_authenticated", False):
        return Store.objects.none()
    if user.is_superuser:
        return Store.objects.order_by("name")
    return user.assigned_stores.order_by("name")


def allowed_store_ids(user) -> list[int]:
    return list(stores_for_user(user).values_list("pk", flat=True))


def user_has_store_access(user) -> bool:
    return stores_for_user(user).exists()


def user_can_pick_stores(user) -> bool:
    """Show store filter UI (more than one accessible store)."""
    return stores_for_user(user).count() > 1


def ensure_session_store_scope(request) -> None:
    """Keep session selection within the user's allowed stores."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return
    allowed = allowed_store_ids(request.user)
    if request.user.is_superuser:
        return
    from core.store_selection import SESSION_KEY

    if not allowed:
        request.session.pop(SESSION_KEY, None)
        request.session.modified = True
        return
    if len(allowed) == 1:
        request.session[SESSION_KEY] = allowed
        request.session.modified = True
        return

    raw = request.session.get(SESSION_KEY)
    if raw is None:
        return
    if not isinstance(raw, list):
        request.session.pop(SESSION_KEY, None)
        request.session.modified = True
        return
    ids = sorted({int(x) for x in raw if int(x) in allowed})
    if not ids or set(ids) == set(allowed):
        request.session.pop(SESSION_KEY, None)
    else:
        request.session[SESSION_KEY] = ids
    request.session.modified = True
