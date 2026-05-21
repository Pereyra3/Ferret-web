from rest_framework import serializers

from warehouse.models import Product


class ProductScanSerializer(serializers.ModelSerializer):
    stock_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "category",
            "department",
            "location",
            "list_price",
            "stock_quantity",
        )

    def get_stock_quantity(self, obj: Product) -> str:
        store = self.context.get("store")
        if store is None:
            return "0"
        return str(obj.stock_quantity(store))
