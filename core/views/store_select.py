from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from core.store_access import stores_for_user, user_can_pick_stores
from core.store_selection import get_selected_store_ids, set_selected_store_ids
from core.views.base import BaseView


class StoreSelectView(BaseView, View):
    """POST: save store filter among stores assigned to the user."""

    template_name = "core/store_select.html"
    page_type = "Tiendas"

    def dispatch(self, request, *args, **kwargs):
        if not user_can_pick_stores(request.user):
            messages.info(
                request,
                "Su cuenta está asignada a una sola tienda; no puede cambiar el filtro.",
            )
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._context())

    def post(self, request, *args, **kwargs):
        if request.POST.get("select_all"):
            set_selected_store_ids(request, None)
            messages.success(request, "Mostrando todas sus tiendas asignadas.")
        else:
            raw = request.POST.getlist("stores")
            try:
                ids = [int(x) for x in raw]
            except ValueError:
                ids = []
            if not ids:
                messages.error(
                    request,
                    "Seleccione al menos una tienda o marque «Todas mis tiendas».",
                )
                return redirect("store_select")
            set_selected_store_ids(request, ids)
            count = len(ids)
            messages.success(
                request,
                f"Filtro aplicado: {count} tienda{'s' if count != 1 else ''}.",
            )
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("home")

    def _context(self):
        stores = list(stores_for_user(self.request.user))
        ids = get_selected_store_ids(self.request)
        all_selected = ids is None
        selected_set = set(ids or [])
        return {
            "type": self.page_type,
            "stores": stores,
            "all_selected": all_selected,
            "selected_ids": selected_set,
            "write_store": self.get_write_store(),
            "next": self.request.GET.get("next", ""),
        }
