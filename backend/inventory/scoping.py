"""Isolation des boutiques (décision D1, option B2) : le filtre « seulement ma boutique » est appliqué ICI, une fois.

Toute vue de l'API métier hérite de ShopScopedViewSet ou de ShopScopedAPIView :
- check_permissions vérifie d'abord l'appartenance à la boutique du jeton (IsShopMember), avant les rôles ;
- get_queryset filtre toujours par la boutique ; les vues fournissent seulement get_base_queryset ;
- perform_create rattache d'office les créations à la boutique ;
- le contexte des serializers reçoit la boutique (choix d'un fournisseur, unicité par boutique).

Protection contre l'oubli (question 6 du brief) :
- une sous-classe qui redéfinit get_queryset ou check_permissions est refusée dès le chargement du code ;
- test_scoping.py vérifie que toutes les vues de l'API, sauf celles de connexion, héritent de ces classes.
"""
from rest_framework import viewsets
from rest_framework.views import APIView

from .roles import IsShopMember, get_membership

PROTECTED_METHODS = ("get_queryset", "check_permissions")


class ShopScopedMixin:
    shop_field = "shop"  # chemin vers la boutique depuis le modèle de la vue (ex. "product__shop")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("_scoping_base"):
            return  # les deux classes de base ci-dessous définissent elles-mêmes ces méthodes
        for name in PROTECTED_METHODS:
            if name in cls.__dict__:
                raise TypeError(f"{cls.__name__} ne doit pas redéfinir {name}() : le filtre par boutique serait "
                                f"contourné. Utilisez get_base_queryset() / get_permissions().")

    def check_permissions(self, request):
        if not IsShopMember().has_permission(request, self):
            self.permission_denied(request)  # non connecté : 401
        super().check_permissions(request)

    @property
    def shop(self):
        return get_membership(self.request).shop

    def scope(self, queryset, field=None):
        return queryset.filter(**{field or self.shop_field: self.shop})


class ShopScopedViewSet(ShopScopedMixin, viewsets.GenericViewSet):
    _scoping_base = True

    def get_base_queryset(self):
        raise NotImplementedError("Chaque vue indique ses données dans get_base_queryset().")

    def get_queryset(self):
        return self.scope(self.get_base_queryset())

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "shop": self.shop}

    def perform_create(self, serializer):
        serializer.save(shop=self.shop)


class ShopScopedAPIView(ShopScopedMixin, APIView):
    """Pour les vues qui calculent elles-mêmes (tableau de bord) : elles filtrent avec self.scope()."""
    _scoping_base = True
