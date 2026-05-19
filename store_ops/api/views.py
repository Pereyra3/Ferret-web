from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Product
from ..views import _store

from .serializers import ProductScanSerializer


class ProductLookupAPIView(APIView):
    """
    GET ?code=<sku or barcode>
    Look up product by exact SKU (case-insensitive).
    """

    def get(self, request, *args, **kwargs):
        code = (request.query_params.get("code") or "").strip()
        if not code:
            return Response({"detail": "Parámetro «code» requerido."}, status=400)
        try:
            store = _store(request)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        product = Product.objects.filter(sku__iexact=code).first()
        if product is None:
            return Response({"detail": "Producto no encontrado."}, status=404)
        ser = ProductScanSerializer(product, context={"request": request, "store": store})
        return Response(ser.data)
