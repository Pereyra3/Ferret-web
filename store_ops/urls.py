from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
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
    path("api/dashboard/sales/", views.api_sales_series, name="api_sales_series"),
    path("api/dashboard/suppliers/", views.api_suppliers_balance, name="api_suppliers_balance"),
    path("api/dashboard/products/", views.api_products_movement, name="api_products_movement"),
]
