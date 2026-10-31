from django.contrib import admin
from .models import Product, Supplier, StockMovement


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email")
    search_fields = ("name", "email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "supplier", "quantity", "selling_price", "is_active")
    list_filter = ("is_active", "supplier")
    search_fields = ("name", "reference", "supplier__name")
    readonly_fields = ("quantity",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("product", "movement_type", "quantity", "unit_price", "created_at")
    list_filter = ("movement_type", "created_at")
    readonly_fields = tuple(field.name for field in StockMovement._meta.fields)
