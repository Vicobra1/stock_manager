from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework import viewsets
from rest_framework.routers import APIRootView

from . import auth_views
from .models import Membership, Product, Shop, ShopToken, StockMovement, Supplier
from .scoping import ShopScopedMixin, ShopScopedViewSet

User = get_user_model()

# Vues volontairement hors boutique : connexion, choix de la boutique, et la page d'accueil de l'API (liste d'adresses).
UNSCOPED_VIEWS = {auth_views.LoginView, auth_views.LogoutView, auth_views.MeView, auth_views.MyShopsView,
                  auth_views.ShopTokenView, APIRootView}


def api_view_classes(patterns=None, prefix=""):
    for pattern in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(pattern, URLResolver):
            yield from api_view_classes(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern) and (prefix + str(pattern.pattern)).startswith("api/"):
            cls = getattr(pattern.callback, "cls", None) or getattr(pattern.callback, "view_class", None)
            if cls is not None:
                yield prefix + str(pattern.pattern), cls


class ForgottenFilterGuardTests(TestCase):
    """Protection contre l'oubli du filtrage par boutique (décision D1, question 6 du brief)."""

    def test_every_business_view_goes_through_the_shop_filter(self):
        checked = 0
        for route, cls in api_view_classes():
            if cls in UNSCOPED_VIEWS or (issubclass(cls, APIRootView)):
                continue
            checked += 1
            self.assertTrue(issubclass(cls, ShopScopedMixin), f"{route} ({cls.__name__}) échappe au filtre par boutique")
        self.assertGreaterEqual(checked, 4)  # produits, fournisseurs, mouvements, tableau de bord

    def test_a_view_cannot_bypass_the_filter(self):
        with self.assertRaises(TypeError):
            class Leaky(ShopScopedViewSet, viewsets.ReadOnlyModelViewSet):  # noqa: F841
                def get_queryset(self):
                    return Product.objects.all()


class ShopIsolationTests(TestCase):
    def setUp(self):
        self.shop_a = Shop.objects.create(name="Boutique A")
        self.shop_b = Shop.objects.create(name="Boutique B")
        self.alice = self.member("alice", self.shop_a)
        self.bob = self.member("bob", self.shop_b)
        self.sup_a = Supplier.objects.create(shop=self.shop_a, name="Fournisseur commun")
        self.sup_b = Supplier.objects.create(shop=self.shop_b, name="Fournisseur commun")
        self.prod_a = Product.objects.create(shop=self.shop_a, name="Secret A", reference="REF-1", supplier=self.sup_a,
                                             purchase_price=10, selling_price=20, quantity=5)
        StockMovement.objects.create(product=self.prod_a, movement_type="sale", quantity=1, unit_price=20)

    def member(self, username, shop):
        user = User.objects.create_user(username)
        Membership.objects.create(user=user, shop=shop, role=Membership.Role.MANAGER)
        return user

    def call(self, user, shop, method, path, body=None):
        token = ShopToken.objects.create(user=user, shop=shop).key
        return getattr(self.client, method)(path, body, content_type="application/json",
                                            HTTP_AUTHORIZATION=f"Token {token}")

    def b(self, method, path, body=None):
        return self.call(self.bob, self.shop_b, method, path, body)

    def rows(self, response):
        data = response.json()
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_lists_only_show_own_data(self):
        self.assertEqual(self.rows(self.b("get", "/api/products/")), [])
        self.assertEqual([s["id"] for s in self.rows(self.b("get", "/api/suppliers/"))], [self.sup_b.id])
        self.assertEqual(self.b("get", "/api/movements/").json()["count"], 0)

    def test_a_foreign_product_is_exactly_like_a_missing_one(self):
        foreign = self.b("get", f"/api/products/{self.prod_a.id}/")
        missing = self.b("get", f"/api/products/{self.prod_a.id + 1000}/")
        self.assertEqual((foreign.status_code, foreign.content), (missing.status_code, missing.content))
        self.assertEqual(foreign.status_code, 404)

    def test_foreign_data_cannot_be_written(self):
        p = f"/api/products/{self.prod_a.id}/"
        for method, path, body in (("patch", p, {"selling_price": 1}), ("post", p + "sale/", {"quantity": 1}),
                                   ("post", p + "entry/", {"quantity": 1}), ("delete", p, None),
                                   ("delete", f"/api/suppliers/{self.sup_a.id}/", None)):
            self.assertEqual(self.b(method, path, body).status_code, 404, f"{method} {path}")
        self.prod_a.refresh_from_db()
        self.assertEqual((self.prod_a.quantity, self.prod_a.selling_price), (5, 20))

    def test_a_non_member_cannot_act_in_a_shop(self):
        self.assertEqual(self.call(self.bob, self.shop_a, "get", "/api/products/").status_code, 404)

    def test_filters_do_not_reach_foreign_data(self):
        for params in (f"?product={self.prod_a.id}", f"?supplier={self.sup_a.id}", "?q=Secret"):
            self.assertEqual(self.b("get", "/api/movements/" + params).json()["count"], 0, params)

    def test_dashboard_only_counts_own_data(self):
        dashboard = self.b("get", "/api/dashboard/").json()
        self.assertEqual(dashboard["products"]["active"], 0)
        self.assertEqual(dashboard["recent_movements"], [])

    def test_creations_belong_to_the_shop_of_the_token_whatever_the_body_says(self):
        body = {"name": "Nouveau", "reference": "N-1", "supplier": self.sup_b.id, "purchase_price": 1,
                "selling_price": 2, "shop": self.shop_a.id}
        self.assertEqual(self.b("post", "/api/products/", body).status_code, 201)
        self.assertEqual(Product.objects.get(reference="N-1").shop, self.shop_b)

    def test_a_product_cannot_use_a_foreign_supplier(self):
        body = {"name": "Nouveau", "reference": "N-2", "supplier": self.sup_a.id, "purchase_price": 1,
                "selling_price": 2}
        self.assertEqual(self.b("post", "/api/products/", body).status_code, 400)

    def test_references_and_supplier_names_are_unique_per_shop_only(self):
        body = {"name": "Même référence", "reference": "REF-1", "supplier": self.sup_b.id, "purchase_price": 1,
                "selling_price": 2}
        self.assertEqual(self.b("post", "/api/products/", body).status_code, 201)  # REF-1 existe chez A : permis
        duplicate = self.b("post", "/api/products/", body)
        self.assertEqual((duplicate.status_code, duplicate.json()["reference"]),
                         (400, ["Une fiche produit porte déjà cette référence."]))
        same_name = self.b("post", "/api/suppliers/", {"name": "Fournisseur commun"})
        self.assertEqual((same_name.status_code, same_name.json()["name"]),
                         (400, ["Un fournisseur porte déjà ce nom dans cette boutique."]))
