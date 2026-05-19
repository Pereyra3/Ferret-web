from django.urls import include, path

from . import views

urlpatterns = [
    path("api/store/", include("store_ops.api.urls", namespace="store_api")),
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("productos/", views.product_list, name="product_list"),
    path("productos/nuevo/", views.product_create, name="product_create"),
    path("productos/<int:pk>/editar/", views.product_edit, name="product_edit"),
    path("inventario/", views.stock_list, name="stock_list"),
    path("inventario/ajuste/", views.stock_adjust, name="stock_adjust"),
    path("ventas/", views.sale_list, name="sale_list"),
    path("ventas/nueva/", views.sale_create, name="sale_create"),
    path("compras/nueva/", views.purchase_create, name="purchase_create"),
    path("pagos/nuevo/", views.payment_create, name="payment_create"),
    path("cierre/", views.eod_view, name="eod"),
    path("api/dashboard/profit/", views.api_profit_series, name="api_profit_series"),
]
