from django.test import TestCase

from . import adapter
from .support import HIDDEN, make_product, make_supplier, product_names, requires_adapter, rows


@requires_adapter
class ScopedRolesTests(TestCase):
    """Le rôle se porte par boutique : gérant chez A et vendeur chez B ne donne pas les mêmes droits."""

    def setUp(self):
        self.shop_a = adapter.create_shop("Boutique A", "alice")
        self.shop_b = adapter.create_shop("Boutique B", "bob")
        adapter.set_plan(self.shop_a, "pro")  # alice + carol + dave : plus que le plan gratuit
        adapter.add_member(self.shop_a, "carol", "manager")
        adapter.add_member(self.shop_a, "dave", "seller")
        adapter.add_member(self.shop_b, "carol", "seller")

        alice, bob = adapter.client("alice", self.shop_a), adapter.client("bob", self.shop_b)
        self.sup_a, self.sup_b = make_supplier(alice, "Fournisseur A"), make_supplier(bob, "Fournisseur B")
        self.prod_a = make_product(alice, self.sup_a, "A-1", name="Produit A", quantity=5)
        self.prod_b = make_product(bob, self.sup_b, "B-1", name="Produit B", quantity=5)

    def new_product_body(self, sup, ref):
        return {"name": "Nouveau", "reference": ref, "supplier": sup, "purchase_price": 1, "selling_price": 2}

    def test_the_same_user_has_a_different_role_in_each_shop(self):
        in_a, in_b = adapter.client("carol", self.shop_a), adapter.client("carol", self.shop_b)
        self.assertEqual(in_a.post("/api/products/", self.new_product_body(self.sup_a, "A-2"), format="json").status_code, 201)
        self.assertEqual(in_b.post("/api/products/", self.new_product_body(self.sup_b, "B-2"), format="json").status_code, 403)
        self.assertEqual(in_a.get("/api/dashboard/").status_code, 200)
        self.assertEqual(in_b.get("/api/dashboard/").status_code, 403)

    def test_the_seller_role_keeps_working_where_it_applies(self):
        in_b = adapter.client("carol", self.shop_b)
        self.assertEqual(in_b.post(f"/api/products/{self.prod_b}/sale/", {"quantity": 1}, format="json").status_code, 201)
        self.assertEqual(in_b.post(f"/api/products/{self.prod_b}/entry/", {"quantity": 1}, format="json").status_code, 403)

    def test_purchase_price_follows_the_role_of_the_shop(self):
        as_manager = rows(adapter.client("carol", self.shop_a).get("/api/products/"))
        as_seller = rows(adapter.client("carol", self.shop_b).get("/api/products/"))
        self.assertTrue(as_manager and all("purchase_price" in p for p in as_manager))
        self.assertTrue(as_seller and all("purchase_price" not in p for p in as_seller))

    def test_a_member_of_one_shop_cannot_act_in_another(self):
        intruder = adapter.client("dave", self.shop_b)  # dave n'est membre que de A
        for method, path, body in (("get", "/api/products/", None), ("get", "/api/movements/", None),
                                   ("get", "/api/dashboard/", None), ("get", "/api/suppliers/", None),
                                   ("post", f"/api/products/{self.prod_b}/sale/", {"quantity": 1}),
                                   ("post", "/api/products/", self.new_product_body(self.sup_b, "B-9"))):
            response = getattr(intruder, method)(path, body, format="json")
            self.assertIn(response.status_code, HIDDEN, f"{method} {path}")
        bob = adapter.client("bob", self.shop_b)
        self.assertEqual(product_names(bob), {"Produit B"})
        self.assertEqual(bob.get(f"/api/products/{self.prod_b}/").json()["quantity"], 5)
