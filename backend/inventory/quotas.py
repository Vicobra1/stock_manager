"""Quotas des plans (décision D5).

- Limites écrites dans le code (option L1) : deux plans fixes, versionnés avec le code.
- Comptage « ticket au guichet » (option C1) : dans une transaction, on écrit d'abord sur la ligne de la boutique,
  puis on compte les vraies données. Deux demandes simultanées pour la même boutique passent donc l'une après l'autre,
  et la seconde voit la création de la première. Avec SQLite, cette écriture prend le verrou d'écriture de la base ;
  avec PostgreSQL, elle verrouille la seule ligne de la boutique (les autres boutiques ne sont pas bloquées).
  Seules les actions soumises à quota passent par là : créer ou réactiver un produit actif, ajouter un membre.
- Refus : code 403 (option choisie), avec "code": "quota_exceeded" dans la réponse pour que l'interface distingue
  un refus de quota d'un refus de droits. Les messages se modifient ci-dessous (QUOTA_MESSAGES).
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

# Messages affichés quand une limite est atteinte : à modifier librement ici.
# Variables disponibles : {plan} (gratuit / Pro) et {limit} (la limite du plan).
QUOTA_MESSAGES = {
    ("products", Shop.Plan.FREE): "Limite du plan {plan} atteinte : {limit} produits actifs. "
                                  "Désactivez un produit ou passez au plan Pro.",
    ("products", Shop.Plan.PRO): "Limite du plan {plan} atteinte : {limit} produits actifs. "
                                 "Désactivez un produit pour libérer une place.",
    ("members", Shop.Plan.FREE): "Limite du plan {plan} atteinte : {limit} membres. Passez au plan Pro pour en ajouter.",
    ("members", Shop.Plan.PRO): "Limite du plan {plan} atteinte : {limit} membres.",
}
QUOTA_CODE = "quota_exceeded"


class QuotaExceeded(APIException):
    """Refus 403 avec un code dédié : {"detail": "<message>", "code": "quota_exceeded"}."""
    status_code = 403
    default_code = QUOTA_CODE

    def __init__(self, message):
        super().__init__({"detail": message, "code": QUOTA_CODE})


def limits(shop):
    return PLAN_LIMITS[shop.plan]


def quota_message(kind, shop):
    return QUOTA_MESSAGES[(kind, shop.plan)].format(plan=PLAN_LABELS[shop.plan], limit=limits(shop)[kind])


def lock_shop(shop):
    """Prend le « ticket » de la boutique pour la fin de la transaction en cours, et relit son plan.

    À appeler à l'intérieur de transaction.atomic(), AVANT toute lecture dans cette transaction : avec SQLite, une
    transaction qui a déjà lu ne peut plus attendre son tour pour écrire.
    """
    Shop.objects.filter(pk=shop.pk).update(plan=F("plan"))
    shop.refresh_from_db(fields=["plan"])  # le plan a pu changer entre-temps


def ensure_product_slot(shop):
    """Refuse (403, quota_exceeded) si la limite de produits actifs est atteinte. Appeler après lock_shop()."""
    if Product.objects.filter(shop=shop, is_active=True).count() >= limits(shop)["products"]:
        raise QuotaExceeded(quota_message("products", shop))


def ensure_member_slot(shop):
    """Refuse (403, quota_exceeded) si la limite de membres est atteinte. Appeler après lock_shop()."""
    if Membership.objects.filter(shop=shop).count() >= limits(shop)["members"]:
        raise QuotaExceeded(quota_message("members", shop))


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
