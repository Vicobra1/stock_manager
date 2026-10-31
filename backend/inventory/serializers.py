from rest_framework import serializers
from .models import Product, Supplier, StockMovement


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


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_reference = serializers.CharField(source="product.reference", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_name", "product_reference", "movement_type",
                  "quantity", "unit_price", "note", "created_at"]
        read_only_fields = fields
