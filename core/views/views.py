from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from core.utils import parse_date_range, range_bounds
from core.views.base import BaseView
from core.views.permissions import CanViewDashboardMixin
from core.views.profit import profit_series, profit_totals
from sales.models import Sale
from warehouse.models import SupplierPayment


class HomeView(BaseView, TemplateView):
    template_name = "core/home.html"
    page_type = "Inicio"


class DashboardView(CanViewDashboardMixin, BaseView, TemplateView):
    template_name = "core/dashboard.html"
    page_type = "Ganancias"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_ids = self.get_store_ids()
        d_from, d_to = parse_date_range(self.request)
        start, end = range_bounds(d_from, d_to)
        context.update(profit_totals(store_ids, start, end))
        context["range_from"] = d_from
        context["range_to"] = d_to
        context["recent_sales"] = (
            self.filter_by_stores(
                Sale.objects.filter(
                    status=Sale.Status.CONFIRMED,
                    created_at__gte=start,
                    created_at__lte=end,
                )
            )
            .select_related("user", "store")
            .order_by("-created_at")[:8]
        )
        context["recent_payments"] = (
            self.filter_by_stores(
                SupplierPayment.objects.filter(
                    created_at__gte=start, created_at__lte=end
                )
            )
            .select_related("supplier", "user", "store")
            .order_by("-created_at")[:8]
        )
        return context


class ApiProfitSeriesView(CanViewDashboardMixin, BaseView, View):
    """GET /api/dashboard/profit/ — chart series JSON."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        store_ids = self.get_store_ids()
        d_from, d_to = parse_date_range(request)
        granularity = request.GET.get("granularity", "day")
        start, end = range_bounds(d_from, d_to)
        data = profit_series(store_ids, start, end, granularity)
        totals = profit_totals(store_ids, start, end)
        return JsonResponse(
            {
                **data,
                "granularity": granularity,
                "totals": {
                    "sales": float(totals["sales_total"]),
                    "payments": float(totals["payments_total"]),
                    "purchases": float(totals["purchases_total"]),
                    "net_cash": float(totals["net_cash"]),
                    "net_operating": float(totals["net_operating"]),
                },
            }
        )
