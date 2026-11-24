"""Temps 2 de la migration multi-boutiques (décision D4) : remplir.

Aller :
- s'il existe déjà des données ou des comptes, créer la boutique « Boxy Box » (plan gratuit) et y rattacher
  tous les fournisseurs et produits ; les mouvements suivent leur produit (option M1) ;
- convertir les rôles : superutilisateur ou groupe « Gérant » → gérant, groupe « Vendeur » → vendeur,
  ni l'un ni l'autre → pas membre ;
- supprimer les groupes « Gérant » et « Vendeur » (option G1).
Sur une base vide (installation neuve, base de test), aucune boutique n'est créée.

Retour (option RA1) : refusé s'il existe plus d'une boutique, pour ne jamais mélanger les données de boutiques
différentes. Sinon, les groupes sont recréés à partir des rôles et la boutique est retirée.
"""
from django.conf import settings
from django.db import migrations

SHOP_NAME = "Boxy Box"
MANAGER_GROUP = "Gérant"
SELLER_GROUP = "Vendeur"
MULTI_SHOP_MESSAGE = ("Retour arrière impossible : plusieurs boutiques existent. Revenir à une seule boutique "
                      "mélangerait leurs données ; restaurez plutôt la sauvegarde faite avant la migration.")


def forward(apps, schema_editor):
    Shop = apps.get_model("inventory", "Shop")
    Membership = apps.get_model("inventory", "Membership")
    Supplier = apps.get_model("inventory", "Supplier")
    Product = apps.get_model("inventory", "Product")
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Group = apps.get_model("auth", "Group")

    if Supplier.objects.exists() or Product.objects.exists() or User.objects.exists():
        shop = Shop.objects.create(name=SHOP_NAME, plan="free")
        Supplier.objects.filter(shop__isnull=True).update(shop=shop)
        Product.objects.filter(shop__isnull=True).update(shop=shop)
        for user in User.objects.all():
            groups = set(user.groups.values_list("name", flat=True))
            if user.is_superuser or MANAGER_GROUP in groups:
                role = "manager"
            elif SELLER_GROUP in groups:
                role = "seller"
            else:
                continue  # aucun rôle aujourd'hui : il ne devient pas membre (écran « Accès en attente »)
            Membership.objects.create(user=user, shop=shop, role=role)

    Group.objects.filter(name__in=[MANAGER_GROUP, SELLER_GROUP]).delete()


def backward(apps, schema_editor):
    Shop = apps.get_model("inventory", "Shop")
    Membership = apps.get_model("inventory", "Membership")
    ShopToken = apps.get_model("inventory", "ShopToken")
    Supplier = apps.get_model("inventory", "Supplier")
    Product = apps.get_model("inventory", "Product")
    Group = apps.get_model("auth", "Group")

    if Shop.objects.count() > 1:
        raise RuntimeError(MULTI_SHOP_MESSAGE)

    manager_group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)
    seller_group, _ = Group.objects.get_or_create(name=SELLER_GROUP)
    for membership in Membership.objects.select_related("user"):
        if membership.role == "seller":
            membership.user.groups.add(seller_group)
        elif not membership.user.is_superuser:  # un superutilisateur était gérant sans groupe
            membership.user.groups.add(manager_group)

    Supplier.objects.update(shop=None)
    Product.objects.update(shop=None)
    ShopToken.objects.all().delete()
    Membership.objects.all().delete()
    Shop.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_shop_columns_empty"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(forward, backward)]
