from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
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


class MovementPagination(LimitOffsetPagination):
    """Pagination de l'historique : ?limit=20&offset=40 (20 lignes par défaut)."""
    default_limit = 20
    max_limit = 200


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Historique des mouvements, filtrable via les paramètres de l'URL :

    - product       : id du produit
    - supplier      : id du fournisseur du produit
    - movement_type : initial | entry | sale | adjustment
    - date_from     : date de début incluse (AAAA-MM-JJ)
    - date_to       : date de fin incluse (AAAA-MM-JJ)
    - q             : recherche dans le nom, la référence du produit et la note
    """
    serializer_class = StockMovementSerializer
    pagination_class = MovementPagination

    def get_queryset(self):
        params = self.request.query_params
        queryset = StockMovement.objects.select_related("product", "product__supplier")

        if params.get("product"):
            queryset = queryset.filter(product_id=self._int("product"))
        if params.get("supplier"):
            queryset = queryset.filter(product__supplier_id=self._int("supplier"))

        movement_type = params.get("movement_type")
        if movement_type:
            if movement_type not in StockMovement.MovementType.values:
                raise ValidationError({"movement_type": "Type de mouvement inconnu."})
            queryset = queryset.filter(movement_type=movement_type)

        date_from, date_to = self._date("date_from"), self._date("date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_from": "La date de début doit précéder la date de fin."})
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        search = params.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search) | Q(product__reference__icontains=search) | Q(note__icontains=search)
            )
        return queryset

    def _int(self, name):
        try:
            return int(self.request.query_params[name])
        except ValueError:
            raise ValidationError({name: "Valeur entière attendue."})

    def _date(self, name):
        value = self.request.query_params.get(name)
        if not value:
            return None
        parsed = parse_date(value)
        if parsed is None:
            raise ValidationError({name: "Date invalide, format attendu : AAAA-MM-JJ."})
        return parsed


def _sales_amounts():
    """Expressions SQL : chiffre d'affaires et bénéfice d'une ligne de vente."""
    money = DecimalField(max_digits=16, decimal_places=2)
    revenue = ExpressionWrapper(F("quantity") * F("unit_price"), output_field=money)
    profit = ExpressionWrapper(F("quantity") * (F("unit_price") - F("product__purchase_price")), output_field=money)
    return revenue, profit


class DashboardView(APIView):
    """Indicateurs du tableau de bord (un seul appel pour tout l'écran)."""

    def get(self, request):
        zero = Decimal("0")
        today = timezone.localdate()
        week_start = today - timedelta(days=6)
        revenue, profit = _sales_amounts()

        active = Product.objects.filter(is_active=True)
        stock = active.aggregate(
            cost=Sum(F("quantity") * F("purchase_price"), output_field=DecimalField(max_digits=18, decimal_places=2)),
            retail=Sum(F("quantity") * F("selling_price"), output_field=DecimalField(max_digits=18, decimal_places=2)),
        )
        low_stock = active.filter(quantity__lte=F("low_stock_threshold")).select_related("supplier").order_by("quantity", "name")

        sales = StockMovement.objects.filter(movement_type=StockMovement.MovementType.SALE)
        today_totals = sales.filter(created_at__date=today).aggregate(
            revenue=Sum(revenue), profit=Sum(profit), units=Sum("quantity"))

        per_day = {row["day"]: row for row in sales.filter(created_at__date__gte=week_start)
                   .annotate(day=TruncDate("created_at"))
                   .values("day").annotate(revenue=Sum(revenue), profit=Sum(profit), units=Sum("quantity"))}
        last_7_days = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            row = per_day.get(day, {})
            last_7_days.append({"date": day.isoformat(), "revenue": row.get("revenue") or zero,
                                "profit": row.get("profit") or zero, "units": row.get("units") or 0})

        top_products = (sales.filter(created_at__date__gte=today - timedelta(days=29))
                        .values("product", "product__name", "product__reference")
                        .annotate(units=Sum("quantity"), revenue=Sum(revenue))
                        .order_by("-units", "product__name")[:5])

        recent = StockMovement.objects.select_related("product")[:6]
        return Response({
            "products": {"active": active.count(), "low_stock": low_stock.count(),
                         "out_of_stock": active.filter(quantity=0).count()},
            "stock_value": {"at_cost": stock["cost"] or zero, "at_retail": stock["retail"] or zero},
            "today": {"revenue": today_totals["revenue"] or zero, "profit": today_totals["profit"] or zero,
                      "units": today_totals["units"] or 0},
            "last_7_days": last_7_days,
            "low_stock_products": ProductSerializer(low_stock[:5], many=True).data,
            "top_products": [{"product": r["product"], "name": r["product__name"],
                              "reference": r["product__reference"], "units": r["units"], "revenue": r["revenue"]}
                             for r in top_products],
            "recent_movements": StockMovementSerializer(recent, many=True).data,
        })
