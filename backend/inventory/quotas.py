"""Quotas des plans (décision D5).

- Limites écrites dans le code (option L1) : deux plans fixes, versionnés avec le code.
- Comptage « ticket au guichet » (option C1) : dans une transaction, on écrit d'abord sur la ligne de la boutique,
  puis on compte les vraies données. Deux demandes simultanées pour la même boutique passent donc l'une après l'autre,
  et la seconde voit la création de la première. Avec SQLite, cette écriture prend le verrou d'écriture de la base ;
  avec PostgreSQL, elle verrouille la seule ligne de la boutique (les autres boutiques ne sont pas bloquées).
  Seules les actions soumises à quota passent par là : créer ou réactiver un produit actif, ajouter un membre.
- Refus : code 402 (option choisie) pour distinguer une limite de plan d'un manque de droits (403).
"""
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import APIException

from .models import Membership, Product, Shop

PLAN_LIMITS = {
    Shop.Plan.FREE: {"products": 20, "members": 2},
    Shop.Plan.PRO: {"products": 1000, "members": 50},
}
PLAN_LABELS = {Shop.Plan.FREE: "gratuit", Shop.Plan.PRO: "Pro"}


class QuotaExceeded(APIException):
    status_code = 402
    default_detail = "Limite du plan atteinte."
    default_code = "quota_exceeded"


def limits(shop):
    return PLAN_LIMITS[shop.plan]


def lock_shop(shop):
    """Prend le « ticket » de la boutique pour la fin de la transaction en cours, et relit son plan.

    À appeler à l'intérieur de transaction.atomic(), AVANT toute lecture dans cette transaction : avec SQLite, une
    transaction qui a déjà lu ne peut plus attendre son tour pour écrire.
    """
    Shop.objects.filter(pk=shop.pk).update(plan=F("plan"))
    shop.refresh_from_db(fields=["plan"])  # le plan a pu changer entre-temps


def ensure_product_slot(shop):
    """Refuse (402) si la boutique a déjà atteint sa limite de produits actifs. Appeler après lock_shop()."""
    limit = limits(shop)["products"]
    if Product.objects.filter(shop=shop, is_active=True).count() >= limit:
        upgrade = " Désactivez un produit ou passez au plan Pro." if shop.plan == Shop.Plan.FREE else \
            " Désactivez un produit pour libérer une place."
        raise QuotaExceeded(f"Limite du plan {PLAN_LABELS[shop.plan]} atteinte : {limit} produits actifs.{upgrade}")


def ensure_member_slot(shop):
    """Refuse (402) si la boutique a déjà atteint sa limite de membres. Appeler après lock_shop()."""
    limit = limits(shop)["members"]
    if Membership.objects.filter(shop=shop).count() >= limit:
        upgrade = " Passez au plan Pro pour en ajouter." if shop.plan == Shop.Plan.FREE else ""
        raise QuotaExceeded(f"Limite du plan {PLAN_LABELS[shop.plan]} atteinte : {limit} membres.{upgrade}")


@transaction.atomic
def add_member(shop, user, role):
    """Ajoute un membre à la boutique, dans la limite du plan (propriétaire compris)."""
    lock_shop(shop)
    ensure_member_slot(shop)
    return Membership.objects.create(shop=shop, user=user, role=role)


@transaction.atomic
def create_shop(name, owner, plan=Shop.Plan.FREE):
    """Crée une boutique et y place son propriétaire comme gérant (il compte parmi les membres)."""
    shop = Shop.objects.create(name=name, plan=plan)
    Membership.objects.create(shop=shop, user=owner, role=Membership.Role.MANAGER)
    return shop


def set_plan(shop, plan):
    """Change le plan. Repasser en gratuit ne supprime rien : seules les nouvelles créations au-delà sont refusées."""
    Shop.objects.filter(pk=shop.pk).update(plan=plan)
    shop.plan = plan
    return shop
