from rest_framework import serializers
from .models import Product, Supplier, StockMovement
from .roles import ROLE_MANAGER, get_role


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "phone", "email", "address", "notes", "created_at"]
        read_only_fields = ["id", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "reference", "supplier", "supplier_name", "purchase_price",
                  "selling_price", "quantity", "low_stock_threshold", "is_low_stock",
                  "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "quantity", "is_low_stock", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Le prix d'achat (et donc la marge) n'est envoyé qu'au gérant. Sans requête dans le contexte,
        # on ne peut pas savoir qui lit : le prix est retiré par prudence.
        if not self._reader_is_manager():
            data.pop("purchase_price", None)
        return data

    def _reader_is_manager(self):
        # Calculé une seule fois par réponse, même pour une liste de produits.
        if "_reader_is_manager" not in self.context:
            request = self.context.get("request")
            self.context["_reader_is_manager"] = get_role(getattr(request, "user", None)) == ROLE_MANAGER
        return self.context["_reader_is_manager"]


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_reference = serializers.CharField(source="product.reference", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_name", "product_reference", "movement_type",
                  "quantity", "unit_price", "note", "created_at"]
        read_only_fields = fields
