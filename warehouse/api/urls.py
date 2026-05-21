from django.urls import path

from warehouse.api.views import ProductLookupAPIView

app_name = "warehouse_api"

urlpatterns = [
    path("products/lookup/", ProductLookupAPIView.as_view(), name="product_lookup"),
]
