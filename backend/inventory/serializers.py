from rest_framework import serializers
from .models import Product, Supplier, StockMovement
from .roles import ROLE_MANAGER, get_role


class ShopUniqueMixin:
    """Unicité au sein de la boutique de la requête (décision D4) : un doublon répond 400, jamais une erreur serveur."""

    def ensure_unique_in_shop(self, field, value, message):
        queryset = self.Meta.model.objects.filter(shop=self.context.get("shop"), **{field: value})
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(message)
        return value


class SupplierSerializer(ShopUniqueMixin, serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "phone", "email", "address", "notes", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        return self.ensure_unique_in_shop("name", value, "Un fournisseur porte déjà ce nom dans cette boutique.")


class ProductSerializer(ShopUniqueMixin, serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "reference", "supplier", "supplier_name", "purchase_price",
                  "selling_price", "quantity", "low_stock_threshold", "is_low_stock",
                  "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "quantity", "is_low_stock", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        # Seuls les fournisseurs de la boutique peuvent être choisis : un fournisseur étranger répond 400.
        if "supplier" in fields and not fields["supplier"].read_only:
            fields["supplier"].queryset = Supplier.objects.filter(shop=self.context.get("shop"))
        return fields

    def validate_reference(self, value):
        return self.ensure_unique_in_shop("reference", value, "Une fiche produit porte déjà cette référence.")

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
            self.context["_reader_is_manager"] = get_role(request) == ROLE_MANAGER
        return self.context["_reader_is_manager"]


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_reference = serializers.CharField(source="product.reference", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_name", "product_reference", "movement_type",
                  "quantity", "unit_price", "note", "created_at"]
        read_only_fields = fields
