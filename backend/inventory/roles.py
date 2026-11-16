"""Rôles de l'application, portés par les groupes Django (attribuables dans l'administration).

- gérant  : tout (groupe « Gérant », ou superutilisateur)
- vendeur : consulte produits, fournisseurs et mouvements, et enregistre des ventes
- aucun groupe : connecté, mais sans accès aux données métier
"""
from rest_framework.permissions import BasePermission

MANAGER_GROUP = "Gérant"
SELLER_GROUP = "Vendeur"
ROLE_MANAGER = "manager"
ROLE_SELLER = "seller"


def get_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_MANAGER
    names = set(user.groups.values_list("name", flat=True))
    if MANAGER_GROUP in names:
        return ROLE_MANAGER
    if SELLER_GROUP in names:
        return ROLE_SELLER
    return None


class _RolePermission(BasePermission):
    message = "Votre compte n'a pas les droits nécessaires pour cette action."
    roles = ()

    def has_permission(self, request, view):
        return get_role(request.user) in self.roles


class IsManager(_RolePermission):
    roles = (ROLE_MANAGER,)


class IsManagerOrSeller(_RolePermission):
    roles = (ROLE_MANAGER, ROLE_SELLER)
