"""Unicité du nom de boutique fiable aussi pour les lettres accentuées (décision D3b).

La contrainte de la migration 0004 comparait LOWER(name) ; or SQLite ne met en minuscules que les lettres sans
accent (« Première » et « PREMIÈRE » restaient différents). On range désormais un nom normalisé par Python
(casefold), et c'est lui que la base garde unique. Avec PostgreSQL, LOWER gère les accents, mais la colonne
normalisée fonctionne pareil partout.
"""
from django.db import migrations, models


def fill_name_key(apps, schema_editor):
    Shop = apps.get_model("inventory", "Shop")
    for shop in Shop.objects.all():
        shop.name_key = shop.name.strip().casefold()
        shop.save(update_fields=["name_key"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0008_shop_required_unique_per_shop"),
    ]

    operations = [
        migrations.AddField(
            model_name="shop",
            name="name_key",
            field=models.CharField(editable=False, max_length=150, null=True),
        ),
        migrations.RunPython(fill_name_key, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="shop",
            name="name_key",
            field=models.CharField(editable=False, max_length=150, unique=True),
        ),
        migrations.RemoveConstraint(
            model_name="shop",
            name="unique_shop_name_case_insensitive",
        ),
    ]
