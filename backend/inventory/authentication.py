"""Authentification par jeton à durée fixe (décision D2).

Deux sortes de jetons arrivent dans le même en-tête « Authorization: Token <clé> » :
- le jeton « compte », obtenu à la connexion (modèle Token de DRF) : il sert à choisir sa boutique ;
- le jeton de boutique (ShopToken), obtenu ensuite : il désigne l'utilisateur ET la boutique.

Les deux expirent settings.TOKEN_LIFETIME après leur création, même s'ils sont utilisés entre-temps.
L'appartenance à la boutique n'est PAS vérifiée ici : un refus à ce niveau répondrait 401, alors qu'un accès à une
boutique dont on n'est pas membre doit être traité comme une donnée introuvable. C'est le rôle de la couche d'accès
aux données.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ShopToken

EXPIRED_MESSAGE = "Votre session a expiré. Veuillez vous reconnecter."


def is_expired(created_at, now=None):
    return created_at + settings.TOKEN_LIFETIME <= (now or timezone.now())


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        now = timezone.now()
        shop_token = ShopToken.objects.select_related("user", "shop").filter(key=key).first()
        if shop_token is not None:
            if not shop_token.user.is_active:
                raise AuthenticationFailed("Utilisateur inactif ou supprimé.")
            if is_expired(shop_token.created_at, now):
                shop_token.delete()
                raise AuthenticationFailed(EXPIRED_MESSAGE)
            # Suivi des connexions : dernière utilisation, sans effet sur l'expiration.
            ShopToken.objects.filter(pk=shop_token.pk).update(last_used_at=now)
            return shop_token.user, shop_token

        user, token = super().authenticate_credentials(key)  # jeton « compte » ; refuse une clé inconnue
        if is_expired(token.created, now):
            token.delete()
            raise AuthenticationFailed(EXPIRED_MESSAGE)
        return user, token
