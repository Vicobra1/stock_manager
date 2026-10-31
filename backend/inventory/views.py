from django.db import transaction
from django.db.models import F
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Product, Supplier, StockMovement
from .serializers import ProductSerializer, SupplierSerializer, StockMovementSerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ["name", "phone", "email"]
    ordering_fields = ["name", "created_at"]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    search_fields = ["name", "reference", "supplier__name"]
    ordering_fields = ["name", "quantity", "selling_price", "created_at"]

    def get_queryset(self):
        queryset = Product.objects.select_related("supplier")
        active = self.request.query_params.get("active")
        low_stock = self.request.query_params.get("low_stock")
        if active in ("true", "false"):
            queryset = queryset.filter(is_active=(active == "true"))
        if low_stock == "true":
            queryset = queryset.filter(quantity__lte=F("low_stock_threshold"))
        return queryset

    def perform_create(self, serializer):
        quantity = self.request.data.get("initial_quantity", 0)
        try:
            quantity = int(quantity)
            if quantity < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError({"initial_quantity": "La quantité initiale doit être un entier positif ou nul."})
        with transaction.atomic():
            product = serializer.save(quantity=quantity)
            if quantity:
                StockMovement.objects.create(product=product, movement_type=StockMovement.MovementType.INITIAL,
                                             quantity=quantity, note="Stock initial")

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        if product.movements.exists():
            return Response({"detail": "Ce produit a un historique de stock. Désactivez-le au lieu de le supprimer."},
                            status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def entry(self, request, pk=None):
        return self._move(request, self.get_object(), StockMovement.MovementType.ENTRY)

    @action(detail=True, methods=["post"])
    def sale(self, request, pk=None):
        return self._move(request, self.get_object(), StockMovement.MovementType.SALE)

    @transaction.atomic
    def _move(self, request, product, movement_type):
        try:
            quantity = int(request.data.get("quantity", 0))
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError({"quantity": "La quantité doit être un entier supérieur à zéro."})
        product = Product.objects.select_for_update().get(pk=product.pk)
        if movement_type == StockMovement.MovementType.SALE and quantity > product.quantity:
            raise ValidationError({"quantity": f"Stock insuffisant. Disponible : {product.quantity}."})
        delta = quantity if movement_type == StockMovement.MovementType.ENTRY else -quantity
        Product.objects.filter(pk=product.pk).update(quantity=F("quantity") + delta)
        product.refresh_from_db()
        movement = StockMovement.objects.create(
            product=product, movement_type=movement_type, quantity=quantity,
            unit_price=request.data.get("unit_price", product.selling_price if movement_type == StockMovement.MovementType.SALE else None),
            note=request.data.get("note", ""),
        )
        return Response({"movement": StockMovementSerializer(movement).data,
                         "product": ProductSerializer(product).data}, status=status.HTTP_201_CREATED)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("product", "product__supplier")
    serializer_class = StockMovementSerializer
    filterset_fields = ["product", "movement_type"]
    ordering_fields = ["created_at", "quantity"]
