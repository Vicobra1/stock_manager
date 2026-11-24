"""Rôles par boutique (décisions D2 et D3, option R1).

Une requête métier se fait avec un jeton de boutique. Le rôle est celui de la personne DANS cette boutique, lu dans
Membership à chaque requête : un changement de rôle s'applique dès la requête suivante. Un superutilisateur n'a de
droits que dans les boutiques dont il est membre (option S2).

- gérant  : tout
- vendeur : consulte produits, fournisseurs et mouvements, et enregistre des ventes
- non-membre : la boutique est introuvable pour lui
"""
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Membership, ShopToken

ROLE_MANAGER = Membership.Role.MANAGER
ROLE_SELLER = Membership.Role.SELLER

CHOOSE_SHOP_MESSAGE = "Choisissez d'abord une boutique."


def get_membership(request):
    """Appartenance de l'utilisateur à la boutique de son jeton, ou None (jeton « compte », non-membre).

    Lue une seule fois par requête, puis gardée sur la requête.
    """
    if request is None:
        return None
    if not hasattr(request, "_shop_membership"):
        membership = None
        token = getattr(request, "auth", None)
        if isinstance(token, ShopToken):
            membership = (Membership.objects.select_related("shop")
                          .filter(user=request.user, shop_id=token.shop_id).first())
        request._shop_membership = membership
    return request._shop_membership


def get_role(request):
    membership = get_membership(request)
    return membership.role if membership else None


class IsShopMember(BasePermission):
    """Première vérification de toute l'API métier.

    - Jeton « compte » : 403, il faut d'abord choisir une boutique.
    - Jeton d'une boutique dont on n'est pas (ou plus) membre : 404, exactement comme une boutique inexistante.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False  # DRF répond 401
        if not isinstance(request.auth, ShopToken):
            raise PermissionDenied(CHOOSE_SHOP_MESSAGE)
        if get_membership(request) is None:
            raise NotFound()
        return True


class _RolePermission(BasePermission):
    message = "Votre compte n'a pas les droits nécessaires pour cette action."
    roles = ()

    def has_permission(self, request, view):
        return get_role(request) in self.roles


class IsManager(_RolePermission):
    roles = (ROLE_MANAGER,)


class IsManagerOrSeller(_RolePermission):
    roles = (ROLE_MANAGER, ROLE_SELLER)
