from django.urls import path

from sales import views

urlpatterns = [
    path("ventas/", views.SaleListView.as_view(), name="sale_list"),
    path("ventas/nueva/", views.SaleCreateView.as_view(), name="sale_create"),
    path("ventas/<int:pk>/editar/", views.SaleUpdateView.as_view(), name="sale_edit"),
    path("ventas/<int:pk>/cobrar/", views.SaleCheckoutView.as_view(), name="sale_checkout"),
    path("ventas/<int:pk>/ticket/", views.PrintSaleView.as_view(), name="print_sale"),
    path("presupuestos/", views.QuoteListView.as_view(), name="quote_list"),
    path("presupuestos/nuevo/", views.QuoteCreateView.as_view(), name="quote_create"),
    path("presupuestos/<int:pk>/editar/", views.QuoteUpdateView.as_view(), name="quote_edit"),
    path("presupuestos/<int:pk>/imprimir/", views.PrintQuoteView.as_view(), name="print_quote"),
    path(
        "presupuestos/<int:pk>/convertir-venta/",
        views.QuoteConvertToSaleView.as_view(),
        name="quote_convert_sale",
    ),
    path("cierre/", views.EodView.as_view(), name="eod"),
    path("cierre/imprimir-ticket/", views.PrintEodSalesView.as_view(), name="print_eod_sales"),
]
