"""Session-based store scope for list views and write operations."""

from core.models import Store
from core.store_access import (
    allowed_store_ids,
    stores_for_user,
    user_can_pick_stores,
    user_has_store_access,
)

SESSION_KEY = "selected_store_ids"


def _valid_ids_for_request(request) -> list[int]:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return []
    if request.user.is_superuser:
        return list(Store.objects.order_by("pk").values_list("pk", flat=True))
    return allowed_store_ids(request.user)


def get_selected_store_ids(request) -> list[int] | None:
    """
    None = all stores the user may access (not necessarily every Store in DB).
    Non-empty list = subset filter.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None
    valid = set(_valid_ids_for_request(request))
    if not valid:
        return []
    if not request.user.is_superuser:
        if len(valid) == 1:
            return list(valid)
    raw = request.session.get(SESSION_KEY)
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    ids = [int(x) for x in raw if int(x) in valid]
    if not valid:
        return []
    if set(ids) == valid:
        return None
    return ids if ids else None


def set_selected_store_ids(request, store_ids: list[int] | None) -> None:
    """Persist selection within the user's allowed stores."""
    valid = set(_valid_ids_for_request(request))
    if not valid:
        request.session.pop(SESSION_KEY, None)
        request.session.modified = True
        return
    if store_ids is None:
        if not request.user.is_superuser and len(valid) == 1:
            request.session[SESSION_KEY] = list(valid)
        else:
            request.session.pop(SESSION_KEY, None)
        request.session.modified = True
        return
    ids = sorted({int(x) for x in store_ids if int(x) in valid})
    if not ids:
        request.session.pop(SESSION_KEY, None)
    elif set(ids) == valid:
        request.session.pop(SESSION_KEY, None)
    else:
        request.session[SESSION_KEY] = ids
    request.session.modified = True


def selected_stores_queryset(request):
    base = stores_for_user(request.user)
    ids = get_selected_store_ids(request)
    if ids is None:
        return base
    return base.filter(pk__in=ids)


def selection_label(request) -> str:
    stores = list(selected_stores_queryset(request))
    if not stores:
        if not user_has_store_access(request.user):
            return "Sin tienda asignada"
        return "Sin tiendas"
    if len(stores) == 1:
        return stores[0].name
    accessible = stores_for_user(request.user).count()
    if len(stores) == accessible and accessible > 1:
        return "Todas mis tiendas"
    names = ", ".join(s.name for s in stores[:3])
    if len(stores) > 3:
        names += f" (+{len(stores) - 3})"
    return names


def show_store_column(request) -> bool:
    if not user_has_store_access(request.user):
        return False
    if stores_for_user(request.user).count() <= 1:
        return False
    ids = get_selected_store_ids(request)
    if ids is None:
        return stores_for_user(request.user).count() > 1
    return len(ids) > 1


def resolve_write_store(request):
    """Single store for new sales, purchases, stock moves, and EOD."""
    from core.utils import get_default_store

    allowed = allowed_store_ids(request.user)
    if not request.user.is_superuser and not allowed:
        raise ValueError(
            "No tiene ninguna tienda asignada. Contacte al administrador."
        )
    ids = get_selected_store_ids(request)
    if ids is not None and len(ids) == 1:
        return Store.objects.get(pk=ids[0])
    if len(allowed) == 1:
        return Store.objects.get(pk=allowed[0])
    if request.user.is_superuser:
        return get_default_store(request)
    if allowed:
        return Store.objects.get(pk=allowed[0])
    raise ValueError("No tiene ninguna tienda asignada. Contacte al administrador.")
