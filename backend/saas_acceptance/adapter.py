"""Pont entre les tests d'acceptation et TON architecture.

Les tests de ce dossier parlent à l'API existante (/api/products/, /api/suppliers/, ...) comme le ferait un vrai
client, sans rien supposer de ta conception : modèle de données, façon d'identifier la boutique (en-tête, jeton,
sous-domaine, préfixe d'URL...), stockage des rôles, etc. Seules les fonctions ci-dessous les relient à ton code.

Remplis-les, puis passe IMPLEMENTED à True. Tant que c'est False, les tests sont ignorés (la suite reste verte).

Règles :
- N'écris pas de logique métier ici : ces fonctions ne font que préparer des données et construire des clients.
  Si tu contournes ton propre code (ex. écrire en base ce que l'API devrait empêcher), le test ne prouve plus rien.
- Ne modifie pas les fichiers test_*.py ni support.py. Si un test te semble faux, argumente-le dans ton ADR.
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from inventory import quotas
from inventory.models import ShopToken

IMPLEMENTED = True

# Limites du plan gratuit (les tests s'appuient sur ces valeurs ; le plan « pro » est très au-dessus).
FREE_MAX_PRODUCTS = 20  # produits ACTIFS par boutique
FREE_MAX_MEMBERS = 2  # membres par boutique, propriétaire compris


class QuotaExceeded(Exception):
    """À lever par add_member() quand la limite de membres du plan est atteinte."""


def create_shop(name, owner_username):
    """Crée une boutique (plan gratuit) et son propriétaire, qui y est gérant.

    Crée l'utilisateur s'il n'existe pas (aucun mot de passe nécessaire). Retourne un objet opaque (« shop »)
    que les tests repassent tels quels aux autres fonctions.
    """
    return quotas.create_shop(name, _user(owner_username))


def add_member(shop, username, role):
    """Ajoute un utilisateur à la boutique avec le rôle "manager" ou "seller" (créé s'il n'existe pas).

    Lève QuotaExceeded si la limite de membres du plan est atteinte.
    """
    try:
        return quotas.add_member(shop, _user(username), role)  # le quota est vérifié par le code de l'application
    except quotas.QuotaExceeded as exc:
        raise QuotaExceeded(str(exc.detail["detail"])) from exc


def set_plan(shop, plan):
    """Passe la boutique au plan "free" ou "pro"."""
    return quotas.set_plan(shop, plan)


def shop_ref(shop):
    """Identifiant de la boutique tel que ton API l'expose (ou, à défaut, tel que tu le stockes en base).

    Les tests l'injectent dans des corps de requête pour vérifier qu'un client ne peut pas choisir sa boutique
    en la déclarant dans les données envoyées.
    """
    return shop.id


def client(username, shop):
    """Retourne un APIClient authentifié comme `username`, qui agit dans `shop`.

    IMPORTANT : cette fonction ne doit PAS vérifier que l'utilisateur appartient à la boutique. Elle doit produire
    les requêtes qu'enverrait un client qui prétend agir dans cette boutique (c'est ton API qui doit le refuser
    si l'utilisateur n'en est pas membre). Un nouveau client à chaque appel.
    """
    # Jeton de boutique créé directement, SANS vérifier l'appartenance : c'est l'API qui doit refuser un non-membre.
    token = ShopToken.objects.create(user=_user(username), shop=shop)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return api


def _user(username):
    """Compte de test sans mot de passe, créé s'il n'existe pas."""
    return get_user_model().objects.get_or_create(username=username)[0]
