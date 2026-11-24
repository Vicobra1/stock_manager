from django.test import TestCase
from rest_framework.test import APIClient

from . import adapter
from .support import make_product, make_supplier, movement_ids, product_names, requires_adapter, rows, sell


@requires_adapter
class IsolationTests(TestCase):
    """Deux boutiques, des données qui se ressemblent exprès : rien ne doit passer de l'une à l'autre.

    La boutique A a plus d'objets que B : l'identifiant le plus élevé de A n'existe donc dans aucune
    représentation de B, quelle que soit ton architecture (identifiants globaux ou par boutique).
    """

    def setUp(self):
        self.shop_a = adapter.create_shop("Boutique A", "alice")
        self.shop_b = adapter.create_shop("Boutique B", "bob")
        self.a = adapter.client("alice", self.shop_a)
        self.b = adapter.client("bob", self.shop_b)

        self.sup_a = [make_supplier(self.a, f"Fournisseur A{i}") for i in (1, 2, 3)]
        self.prod_a1 = make_product(self.a, self.sup_a[0], "REF-1", name="Zinc secret A", quantity=10, purchase=100, selling=150)
        self.prod_a2 = make_product(self.a, self.sup_a[1], "REF-2", name="Padding 2")
        self.prod_a3 = make_product(self.a, self.sup_a[2], "REF-3", name="Padding 3")
        for _ in range(3):
            sell(self.a, self.prod_a1, 1)  # 3 ventes de 150 : chiffre d'affaires 450, stock 7

        self.sup_b = make_supplier(self.b, "Fournisseur B1")
        self.prod_b1 = make_product(self.b, self.sup_b, "REF-1", name="Cuivre B", quantity=4, purchase=10, selling=20)
        sell(self.b, self.prod_b1, 1)  # chiffre d'affaires 20, stock 3

        self.mov_a = movement_ids(self.a)  # 4 mouvements : stock initial + 3 ventes
        self.mov_b = movement_ids(self.b)  # 2 mouvements
        self.foreign_movement = max(self.mov_a)

    def test_lists_only_contain_own_data(self):
        self.assertEqual(product_names(self.b), {"Cuivre B"})
        self.assertEqual(product_names(self.a), {"Zinc secret A", "Padding 2", "Padding 3"})
        self.assertEqual({s["name"] for s in rows(self.b.get("/api/suppliers/"))}, {"Fournisseur B1"})
        self.assertEqual((len(self.mov_a), len(self.mov_b)), (4, 2))
        self.assertTrue(self.mov_a.isdisjoint(self.mov_b))

    def test_pagination_counts_do_not_leak(self):
        self.assertEqual(self.b.get("/api/movements/", {"limit": 1}).json()["count"], 2)
        self.assertEqual(self.a.get("/api/movements/", {"limit": 1}).json()["count"], 4)

    def test_foreign_objects_are_not_found(self):
        for path in (f"/api/products/{self.prod_a3}/", f"/api/suppliers/{self.sup_a[2]}/",
                     f"/api/movements/{self.foreign_movement}/"):
            self.assertEqual(self.b.get(path).status_code, 404, path)

    def test_a_foreign_object_is_indistinguishable_from_a_missing_one(self):
        # Sinon un attaquant peut énumérer les identifiants des autres boutiques (oracle d'existence).
        for template, foreign in (("/api/products/{}/", self.prod_a3), ("/api/suppliers/{}/", self.sup_a[2]),
                                  ("/api/movements/{}/", self.foreign_movement)):
            real = self.b.get(template.format(foreign))
            missing = self.b.get(template.format(foreign + 100000))
            self.assertEqual(real.status_code, missing.status_code, template)
            self.assertEqual(real.content, missing.content, template)

    def test_foreign_objects_cannot_be_written(self):
        attempts = [
            ("patch", f"/api/products/{self.prod_a1}/", {"selling_price": 1}),
            ("delete", f"/api/products/{self.prod_a3}/", None),  # sans mouvement : sa suppression réussirait
            ("post", f"/api/products/{self.prod_a1}/sale/", {"quantity": 1}),
            ("post", f"/api/products/{self.prod_a1}/entry/", {"quantity": 1}),
            ("patch", f"/api/suppliers/{self.sup_a[2]}/", {"name": "Piraté"}),
            ("delete", f"/api/suppliers/{self.sup_a[2]}/", None),
        ]
        for method, path, body in attempts:
            response = getattr(self.b, method)(path, body, format="json")
            self.assertEqual(response.status_code, 404, f"{method} {path}")
        mine = self.a.get(f"/api/products/{self.prod_a1}/").json()
        self.assertEqual((mine["quantity"], float(mine["selling_price"])), (7, 150.0))
        self.assertEqual(self.a.get(f"/api/products/{self.prod_a3}/").status_code, 200)
        self.assertEqual(self.a.get(f"/api/suppliers/{self.sup_a[2]}/").json()["name"], "Fournisseur A3")
        self.assertEqual(movement_ids(self.a), self.mov_a)

    def test_a_product_cannot_be_linked_to_a_foreign_supplier(self):
        body = {"name": "Intrus", "reference": "X-1", "supplier": self.sup_a[0], "purchase_price": 1, "selling_price": 2}
        self.assertIn(self.b.post("/api/products/", body, format="json").status_code, (400, 404))
        self.assertEqual(product_names(self.b), {"Cuivre B"})
        response = self.b.patch(f"/api/products/{self.prod_b1}/", {"supplier": self.sup_a[0]}, format="json")
        self.assertIn(response.status_code, (400, 404))
        self.assertEqual(self.b.get(f"/api/products/{self.prod_b1}/").json()["supplier"], self.sup_b)

    def test_the_shop_cannot_be_chosen_through_the_request_body(self):
        # Mass assignment : le client ne doit pas pouvoir désigner la boutique propriétaire d'un objet.
        ref = adapter.shop_ref(self.shop_a)
        for field in ("shop", "shop_id", "tenant", "tenant_id", "organization", "organization_id", "owner", "account"):
            body = {"name": f"Via {field}", "reference": f"MA-{field}", "supplier": self.sup_b,
                    "purchase_price": 1, "selling_price": 2, field: ref}
            response = self.b.post("/api/products/", body, format="json")
            self.assertIn(response.status_code, (201, 400), field)
            self.assertNotIn(f"Via {field}", product_names(self.a), field)
            if response.status_code == 201:
                self.assertIn(f"Via {field}", product_names(self.b), field)

    def test_filters_and_search_do_not_reach_foreign_data(self):
        for params in ({"product": self.prod_a1}, {"supplier": self.sup_a[0]}, {"q": "Zinc"}, {"q": "REF-3"},
                       {"product": self.prod_a1, "movement_type": "sale"}):
            response = self.b.get("/api/movements/", params)
            if response.status_code == 200:
                self.assertEqual(response.json()["count"], 0, params)
            else:
                self.assertIn(response.status_code, (400, 404), params)

    def test_dashboard_only_counts_own_data(self):
        a, b = self.a.get("/api/dashboard/").json(), self.b.get("/api/dashboard/").json()
        self.assertEqual((a["products"]["active"], b["products"]["active"]), (3, 1))
        self.assertEqual((float(a["today"]["revenue"]), float(b["today"]["revenue"])), (450.0, 20.0))
        self.assertEqual((float(a["stock_value"]["at_cost"]), float(b["stock_value"]["at_cost"])), (700.0, 30.0))
        self.assertEqual({m["id"] for m in b["recent_movements"]} - self.mov_b, set())
        self.assertEqual({p["product"] for p in b["top_products"]}, {self.prod_b1})
        self.assertEqual({p["product"] for p in a["top_products"]}, {self.prod_a1})

    def test_unique_constraints_are_scoped_to_the_shop(self):
        # « REF-1 » existe déjà dans A ET dans B ; « REF-3 » seulement dans A.
        sup = make_supplier(self.b, "Fournisseur A1")  # même nom qu'un fournisseur de A : autorisé
        self.assertIsNotNone(make_product(self.b, sup, "REF-3", name="REF-3 chez B"))
        for client, path, body in (
            (self.a, "/api/products/", {"name": "Doublon", "reference": "REF-1", "supplier": self.sup_a[0],
                                        "purchase_price": 1, "selling_price": 2}),
            (self.b, "/api/products/", {"name": "Doublon", "reference": "REF-1", "supplier": self.sup_b,
                                        "purchase_price": 1, "selling_price": 2}),
            (self.a, "/api/suppliers/", {"name": "Fournisseur A1"}),
            (self.b, "/api/suppliers/", {"name": "Fournisseur B1"}),
        ):
            # 400 attendu, jamais une erreur serveur (le client de test relève une exception en cas de 500).
            self.assertEqual(client.post(path, body, format="json").status_code, 400, (path, body["name"]))

    def test_unauthenticated_requests_see_nothing(self):
        for path in ("/api/products/", "/api/suppliers/", "/api/movements/", "/api/dashboard/"):
            self.assertEqual(APIClient().get(path).status_code, 401, path)
