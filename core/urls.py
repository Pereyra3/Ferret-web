from django.urls import path

from core.views.store_select import StoreSelectView
from core.views.views import ApiProfitSeriesView, DashboardView, HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/dashboard/profit/", ApiProfitSeriesView.as_view(), name="api_profit_series"),
    path("tiendas/seleccion/", StoreSelectView.as_view(), name="store_select"),
]
