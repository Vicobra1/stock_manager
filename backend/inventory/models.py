import secrets

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.core.validators import MinValueValidator


class Supplier(models.Model):
    shop = models.ForeignKey("Shop", on_delete=models.PROTECT, related_name="suppliers")
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Nom unique au sein d'une boutique seulement (deux boutiques peuvent avoir le même fournisseur).
            models.UniqueConstraint(fields=["shop", "name"], name="unique_supplier_name_per_shop"),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    shop = models.ForeignKey("Shop", on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200, db_index=True)
    reference = models.CharField(max_length=80)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="products")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Référence unique au sein d'une boutique seulement.
            models.UniqueConstraint(fields=["shop", "reference"], name="unique_product_reference_per_shop"),
        ]

    def __str__(self):
        return f"{self.name} ({self.reference})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.low_stock_threshold


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        INITIAL = "initial", "Stock initial"
        ENTRY = "entry", "Entrée"
        SALE = "sale", "Vente"
        ADJUSTMENT = "adjustment", "Ajustement"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=12, choices=MovementType.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.product} × {self.quantity}"


class Shop(models.Model):
    """Une boutique cliente du service. Ses données sont isolées de celles des autres boutiques."""

    class Plan(models.TextChoices):
        FREE = "free", "Gratuit"
        PRO = "pro", "Pro"

    name = models.CharField(max_length=150)
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.FREE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "boutique"
        constraints = [
            # Deux boutiques ne peuvent pas porter le même nom, majuscules comprises (décision D3b).
            models.UniqueConstraint(Lower("name"), name="unique_shop_name_case_insensitive",
                                    violation_error_message="Une boutique porte déjà ce nom."),
        ]

    def __str__(self):
        return self.name


class Membership(models.Model):
    """Appartenance d'un utilisateur à une boutique, avec son rôle dans CETTE boutique (décision D3, option R1)."""

    class Role(models.TextChoices):
        MANAGER = "manager", "Gérant"
        SELLER = "seller", "Vendeur"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membre"
        constraints = [
            # Un seul rôle par personne et par boutique, garanti par la base elle-même.
            models.UniqueConstraint(fields=["user", "shop"], name="unique_membership_per_shop"),
        ]

    def __str__(self):
        return f"{self.user} · {self.shop} · {self.get_role_display()}"


class ShopToken(models.Model):
    """Jeton de connexion propre à une boutique (décision D2) : il désigne à la fois l'utilisateur et la boutique.

    Valable settings.TOKEN_LIFETIME (12 h) après sa création, quelle que soit son utilisation. L'appartenance et le
    rôle ne sont pas figés dans le jeton : ils sont relus à chaque requête.
    """

    key = models.CharField(max_length=40, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shop_tokens")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)  # suivi des connexions, sans effet sur l'expiration

    class Meta:
        verbose_name = "jeton de boutique"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(20)
        super().save(*args, **kwargs)

    @property
    def expires_at(self):
        return self.created_at + settings.TOKEN_LIFETIME

    def __str__(self):
        return f"{self.user} · {self.shop}"
