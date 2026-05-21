from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core.store_selection import resolve_write_store
from warehouse.api.serializers import ProductScanSerializer
from warehouse.models import Product


class ProductLookupAPIView(APIView):
    """GET ?code=<sku or barcode> — product lookup for POS scanning."""

    def get(self, request, *args, **kwargs):
        if not request.user.has_perm("warehouse.view_product"):
            raise PermissionDenied("Sin permiso para consultar productos.")
        code = (request.query_params.get("code") or "").strip()
        if not code:
            return Response({"detail": "Parámetro «code» requerido."}, status=400)
        try:
            store = resolve_write_store(request)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        product = Product.objects.filter(sku__iexact=code).first()
        if product is None:
            return Response({"detail": "Producto no encontrado."}, status=404)
        ser = ProductScanSerializer(product, context={"request": request, "store": store})
        return Response(ser.data)
