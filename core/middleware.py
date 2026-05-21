from django.conf import settings
from django.utils.functional import SimpleLazyObject

from core.models import Store
from core.store_access import ensure_session_store_scope


def _resolve_default_store():
    code = getattr(settings, "DEFAULT_STORE_CODE", "principal")
    s = Store.objects.filter(code=code).first()
    if s:
        return s
    return Store.objects.filter(is_default=True).first()


class DefaultStoreMiddleware:
    """Attach default Store to request (v1: single visible store)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.default_store = SimpleLazyObject(_resolve_default_store)
            ensure_session_store_scope(request)
        else:
            request.default_store = None
        return self.get_response(request)
