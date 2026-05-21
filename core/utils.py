from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.functional import SimpleLazyObject, empty


def get_default_store(request):
    """Resolve default store (middleware attaches a SimpleLazyObject)."""
    store = getattr(request, "default_store", None)
    if store is None:
        raise ValueError("No default store. Sign in or run: python manage.py setup_defaults")
    if isinstance(store, SimpleLazyObject):
        if store._wrapped is empty:
            store._setup()
        store = store._wrapped
    if store is None:
        raise ValueError(
            "No store in database (DEFAULT_STORE_CODE or is_default). "
            "Run: python manage.py setup_defaults"
        )
    return store


def parse_date_range(request):
    today = timezone.localdate()
    default_from = today - timedelta(days=30)
    from_s = request.GET.get("from")
    to_s = request.GET.get("to")
    try:
        d_from = date.fromisoformat(from_s) if from_s else default_from
    except ValueError:
        d_from = default_from
    try:
        d_to = date.fromisoformat(to_s) if to_s else today
    except ValueError:
        d_to = today
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    return d_from, d_to


def range_bounds(d_from, d_to):
    start = timezone.make_aware(datetime.combine(d_from, time.min))
    end = timezone.make_aware(datetime.combine(d_to, time.max))
    return start, end
