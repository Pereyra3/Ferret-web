from rest_framework import serializers

from ..models import Product


class ProductScanSerializer(serializers.ModelSerializer):
    """Producto devuelto al escanear (caja / API)."""

    stock_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "sku", "name", "category", "list_price", "stock_quantity")

    def get_stock_quantity(self, obj: Product) -> str:
        store = self.context.get("store")
        if store is None:
            return "0"
        qty = obj.stock_quantity(store)
        return str(qty)
