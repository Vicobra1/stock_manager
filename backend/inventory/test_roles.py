from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.authtoken.models import Token

from .models import Product, Supplier
from .roles import get_role

User = get_user_model()


class RoleTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="Fournisseur A")
        self.product = Product.objects.create(name="Riz", reference="RIZ-1", supplier=self.supplier,
                                              purchase_price=100, selling_price=150, quantity=10)
        self.manager = self.make_user("gerant", "Gérant")
        self.seller = self.make_user("vendeur", "Vendeur")
        self.nobody = self.make_user("sans-role")

    def make_user(self, username, group=None):
        user = User.objects.create_user(username)  # pas de mot de passe : inutile ici, et beaucoup plus rapide
        if group:
            user.groups.add(Group.objects.get(name=group))
        return user

    def call(self, user, method, path, body=None):
        headers = {"HTTP_AUTHORIZATION": f"Token {Token.objects.get_or_create(user=user)[0].key}"} if user else {}
        return getattr(self.client, method)(path, body, content_type="application/json", **headers)

    def product_body(self, reference="NEW-1"):
        return {"name": "Nouveau", "reference": reference, "supplier": self.supplier.id,
                "purchase_price": 10, "selling_price": 20, "initial_quantity": 3}

    def test_groups_exist_after_migration(self):
        self.assertEqual(set(Group.objects.values_list("name", flat=True)), {"Gérant", "Vendeur"})

    def test_get_role(self):
        self.assertEqual(get_role(self.manager), "manager")
        self.assertEqual(get_role(self.seller), "seller")
        self.assertIsNone(get_role(self.nobody))
        self.assertEqual(get_role(User.objects.create_superuser("root", password="x")), "manager")

    def test_me_exposes_the_role(self):
        for user, role in ((self.manager, "manager"), (self.seller, "seller"), (self.nobody, None)):
            response = self.call(user, "get", "/api/auth/me/")
            self.assertEqual((response.status_code, response.json()["role"]), (200, role), user.username)

    def test_manager_can_do_everything(self):
        p = f"/api/products/{self.product.id}/"
        self.assertEqual(self.call(self.manager, "get", "/api/products/").status_code, 200)
        self.assertEqual(self.call(self.manager, "get", "/api/dashboard/").status_code, 200)
        self.assertEqual(self.call(self.manager, "post", "/api/suppliers/", {"name": "Autre"}).status_code, 201)
        self.assertEqual(self.call(self.manager, "post", "/api/products/", self.product_body()).status_code, 201)
        self.assertEqual(self.call(self.manager, "patch", p, {"selling_price": 160}).status_code, 200)
        self.assertEqual(self.call(self.manager, "post", p + "entry/", {"quantity": 5}).status_code, 201)
        self.assertEqual(self.call(self.manager, "post", p + "sale/", {"quantity": 1}).status_code, 201)
        spare = Product.objects.create(name="Jetable", reference="X", supplier=self.supplier,
                                       purchase_price=1, selling_price=2)
        self.assertEqual(self.call(self.manager, "delete", f"/api/products/{spare.id}/").status_code, 204)

    def test_seller_can_read_and_sell(self):
        for path in ("/api/products/", f"/api/products/{self.product.id}/", "/api/suppliers/", "/api/movements/"):
            self.assertEqual(self.call(self.seller, "get", path).status_code, 200, path)
        sale = self.call(self.seller, "post", f"/api/products/{self.product.id}/sale/", {"quantity": 2})
        self.assertEqual(sale.status_code, 201)
        self.assertEqual(sale.json()["product"]["quantity"], 8)

    def test_seller_always_sells_at_the_catalogue_price(self):
        response = self.call(self.seller, "post", f"/api/products/{self.product.id}/sale/", {"quantity": 1, "unit_price": "1"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.json()["movement"]["unit_price"]), Decimal("150"))

    def test_manager_can_still_set_a_sale_price(self):
        response = self.call(self.manager, "post", f"/api/products/{self.product.id}/sale/", {"quantity": 1, "unit_price": "120"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.json()["movement"]["unit_price"]), Decimal("120"))

    def test_seller_still_cannot_oversell(self):
        response = self.call(self.seller, "post", f"/api/products/{self.product.id}/sale/", {"quantity": 99})
        self.assertEqual(response.status_code, 400)

    def test_seller_cannot_modify_catalogue_or_stock(self):
        p = f"/api/products/{self.product.id}/"
        forbidden = [
            ("post", "/api/products/", self.product_body()),
            ("patch", p, {"selling_price": 1}),
            ("patch", p, {"is_active": False}),
            ("delete", p, None),
            ("post", p + "entry/", {"quantity": 5}),
            ("post", "/api/suppliers/", {"name": "Autre"}),
            ("patch", f"/api/suppliers/{self.supplier.id}/", {"name": "Renommé"}),
            ("delete", f"/api/suppliers/{self.supplier.id}/", None),
            ("get", "/api/dashboard/", None),
        ]
        for method, path, body in forbidden:
            self.assertEqual(self.call(self.seller, method, path, body).status_code, 403, f"{method} {path}")
        self.product.refresh_from_db()
        self.assertEqual((self.product.quantity, self.product.selling_price), (10, 150))

    def test_user_without_role_has_no_access_to_business_data(self):
        for method, path, body in (("get", "/api/products/", None), ("get", "/api/suppliers/", None),
                                   ("get", "/api/movements/", None), ("get", "/api/dashboard/", None),
                                   ("post", f"/api/products/{self.product.id}/sale/", {"quantity": 1})):
            self.assertEqual(self.call(self.nobody, method, path, body).status_code, 403, f"{method} {path}")

    def test_user_without_role_can_still_logout(self):
        self.assertEqual(self.call(self.nobody, "post", "/api/auth/logout/").status_code, 204)

    def test_forbidden_message_is_in_french(self):
        detail = self.call(self.seller, "get", "/api/dashboard/").json()["detail"]
        self.assertEqual(detail, "Votre compte n'a pas les droits nécessaires pour cette action.")

    def test_anonymous_still_gets_401(self):
        self.assertEqual(self.call(None, "get", "/api/products/").status_code, 401)
