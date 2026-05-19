from django.urls import path

from .views import ProductLookupAPIView

app_name = "store_api"

urlpatterns = [
    path(
        "products/lookup/",
        ProductLookupAPIView.as_view(),
        name="product_lookup",
    ),
]
