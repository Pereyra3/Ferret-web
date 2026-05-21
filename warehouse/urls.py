from django.urls import path

from warehouse import views

urlpatterns = [
    path("productos/", views.ProductListView.as_view(), name="product_list"),
    path("productos/nuevo/", views.ProductCreateView.as_view(), name="product_create"),
    path("productos/<int:pk>/editar/", views.ProductUpdateView.as_view(), name="product_edit"),
    path("inventario/", views.StockListView.as_view(), name="stock_list"),
    path(
        "inventario/imprimir-sugerido/",
        views.PrintStockSuggestedView.as_view(),
        name="print_stock_suggested",
    ),
    path("inventario/ajuste/", views.StockAdjustView.as_view(), name="stock_adjust"),
    path(
        "inventario/transferencias/",
        views.StockTransferListView.as_view(),
        name="stock_transfer_list",
    ),
    path(
        "inventario/transferencia/",
        views.StockTransferCreateView.as_view(),
        name="stock_transfer_create",
    ),
    path(
        "inventario/transferencia/<int:pk>/aceptar/",
        views.StockTransferAcceptView.as_view(),
        name="stock_transfer_accept",
    ),
    path(
        "inventario/transferencia/<int:pk>/rechazar/",
        views.StockTransferRejectView.as_view(),
        name="stock_transfer_reject",
    ),
    path("inventario/importar/", views.StockImportView.as_view(), name="stock_import"),
    path(
        "inventario/importar/plantilla.xlsx",
        views.StockImportSampleView.as_view(),
        name="stock_import_sample",
    ),
    path("compras/nueva/", views.PurchaseCreateView.as_view(), name="purchase_create"),
    path("pagos/nuevo/", views.PaymentCreateView.as_view(), name="payment_create"),
]
