"""Temps 3 de la migration multi-boutiques (décision D4) : rendre la boutique obligatoire et l'unicité locale.

Le nom de fournisseur et la référence produit ne sont plus uniques dans toute la base, mais au sein d'une boutique.
La dernière opération ne fait rien à l'aller ; au retour elle s'exécute EN PREMIER (Django inverse l'ordre) et refuse
de revenir en arrière s'il existe plusieurs boutiques (option RA1) : rétablir l'unicité globale échouerait ou
mélangerait des données de boutiques différentes.
"""
import django.db.models.deletion
from django.db import migrations, models

MULTI_SHOP_MESSAGE = ("Retour arrière impossible : plusieurs boutiques existent. Revenir à une seule boutique "
                      "mélangerait leurs données ; restaurez plutôt la sauvegarde faite avant la migration.")


def refuse_if_several_shops(apps, schema_editor):
    if apps.get_model("inventory", "Shop").objects.count() > 1:
        raise RuntimeError(MULTI_SHOP_MESSAGE)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_fill_boxy_box"),
    ]

    operations = [
        migrations.AlterField(
            model_name="supplier",
            name="shop",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="suppliers",
                                    to="inventory.shop"),
        ),
        migrations.AlterField(
            model_name="product",
            name="shop",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products",
                                    to="inventory.shop"),
        ),
        migrations.AlterField(
            model_name="supplier",
            name="name",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="product",
            name="reference",
            field=models.CharField(max_length=80),
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(fields=("shop", "name"), name="unique_supplier_name_per_shop"),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(fields=("shop", "reference"), name="unique_product_reference_per_shop"),
        ),
        migrations.RunPython(migrations.RunPython.noop, refuse_if_several_shops),
    ]
