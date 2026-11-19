from django import forms
from django.contrib import admin
from django.db.models import Count, Q

from .models import Membership, Product, Shop, StockMovement, Supplier
from .quotas import limits, quota_message


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "phone", "email")
    list_filter = ("shop",)
    search_fields = ("name", "email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "shop", "supplier", "quantity", "selling_price", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("name", "reference", "supplier__name")
    readonly_fields = ("quantity",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("product", "movement_type", "quantity", "unit_price", "created_at")
    list_filter = ("product__shop", "movement_type", "created_at")
    readonly_fields = tuple(field.name for field in StockMovement._meta.fields)


# --- Boutiques et membres -------------------------------------------------------------------------------------------
# L'admin applique les mêmes règles que l'API : nom de boutique unique (accents et majuscules compris) et limite de
# membres du plan. Changer le plan ne supprime rien (décision D5) : seules les nouvelles créations au-delà sont refusées.
# L'admin n'est utilisé que par le superutilisateur : les ajouts ne prennent pas le « ticket » de la boutique
# (verrou contre les demandes simultanées), contrairement à l'API.


class ShopAdminForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ("name", "plan")

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        taken = Shop.objects.filter(name_key=Shop.normalize_name(name)).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("Une boutique porte déjà ce nom.")
        return name


def member_limit_error(shop, count):
    """Message de refus si `count` membres dépassent la limite du plan de `shop`, sinon None."""
    return quota_message("members", shop) if count > limits(shop)["members"] else None


class MembershipInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        kept = [form for form in self.forms
                if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("user")]
        # Seuls les nouveaux membres demandent une place : repasser en gratuit au-dessus de la limite garde tout le monde.
        # self.instance porte déjà le plan choisi dans le formulaire de la boutique.
        if any(form.instance.pk is None for form in kept):
            error = member_limit_error(self.instance, len(kept))
            if error:
                raise forms.ValidationError(error)


class MembershipInline(admin.TabularInline):
    model = Membership
    formset = MembershipInlineFormSet
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user",)
    extra = 0


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    form = ShopAdminForm
    list_display = ("name", "plan", "members", "active_products", "created_at")
    list_filter = ("plan",)
    search_fields = ("name",)
    inlines = (MembershipInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            member_count=Count("memberships", distinct=True),
            active_product_count=Count("products", filter=Q(products__is_active=True), distinct=True),
        )

    @admin.display(description="membres")
    def members(self, shop):
        return f"{shop.member_count} / {limits(shop)['members']}"

    @admin.display(description="produits actifs")
    def active_products(self, shop):
        return f"{shop.active_product_count} / {limits(shop)['products']}"


class MembershipAdminForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("user", "shop", "role")

    def clean(self):
        data = super().clean()
        shop = data.get("shop")
        # La limite ne joue que pour une nouvelle place : un ajout, ou le déplacement vers une autre boutique.
        if shop and (self.instance.pk is None or self.instance.shop_id != shop.pk):
            error = member_limit_error(shop, Membership.objects.filter(shop=shop).count() + 1)
            if error:
                raise forms.ValidationError(error)
        return data


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    form = MembershipAdminForm
    list_display = ("user", "shop", "role", "created_at")
    list_filter = ("shop", "role")
    search_fields = ("user__username", "user__first_name", "user__last_name", "shop__name")
    autocomplete_fields = ("user", "shop")

