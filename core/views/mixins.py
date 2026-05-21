"""Shared mixins for ferreteria CBVs (pattern aligned with tech_tool)."""

from core.store_access import allowed_store_ids
from core.store_selection import (
    get_selected_store_ids,
    resolve_write_store,
    selected_stores_queryset,
    selection_label,
    show_store_column,
)


class DefaultStoreMixin:
    """
    Store scope: session filter for reads, single write store for mutations.
    get_store() = write store (sales, purchases, EOD, adjustments).
    """

    def get_selected_stores(self):
        if not hasattr(self, "_cached_selected_stores"):
            self._cached_selected_stores = selected_stores_queryset(self.request)
        return self._cached_selected_stores

    def get_store_ids(self):
        if not hasattr(self, "_cached_store_ids"):
            ids = get_selected_store_ids(self.request)
            if ids is None:
                self._cached_store_ids = allowed_store_ids(self.request.user)
            else:
                self._cached_store_ids = ids
        return self._cached_store_ids

    def filter_by_stores(self, queryset, field="store"):
        return queryset.filter(**{f"{field}__in": self.get_store_ids()})

    def get_store_filter_kwargs(self, field="store"):
        return {f"{field}__in": self.get_store_ids()}

    def get_write_store(self):
        if not hasattr(self, "_cached_write_store"):
            self._cached_write_store = resolve_write_store(self.request)
        return self._cached_write_store

    def get_store(self):
        """Store used when creating sales, purchases, payments, stock, EOD."""
        return self.get_write_store()

    def get_store_selection_label(self):
        return selection_label(self.request)

    def show_store_column(self):
        return show_store_column(self.request)

    def uses_write_store_hint(self):
        ids = get_selected_store_ids(self.request)
        return ids is None or len(ids) != 1


class PageContextMixin:
    """
    Shell context: type (nav label), optional title for form pages.
    Mirrors tech_tool context['type'] / page_title pattern.
    """

    page_type = ""
    page_title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.page_type:
            context["type"] = self.page_type
        if self.page_title:
            context["title"] = self.page_title
        return context
