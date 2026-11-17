from django.test import TestCase

from . import adapter
from .support import REJECTED, active_product_count, make_product, make_supplier, product_names, requires_adapter

LIMIT = adapter.FREE_MAX_PRODUCTS


def body(sup, ref):
    return {"name": f"Produit {ref}", "reference": ref, "supplier": sup, "purchase_price": 1, "selling_price": 2}


@requires_adapter
class QuotaTests(TestCase):
    """Plan gratuit : LIMIT produits actifs et FREE_MAX_MEMBERS membres par boutique. Plan « pro » : très au-dessus."""

    def setUp(self):
        self.shop = adapter.create_shop("Boutique pleine", "owner")
        self.c = adapter.client("owner", self.shop)
        self.sup = make_supplier(self.c, "Fournisseur")
        self.ids = [make_product(self.c, self.sup, f"P-{i}") for i in range(LIMIT)]

    def test_the_free_plan_stops_at_the_limit(self):
        self.assertEqual(active_product_count(self.c), LIMIT)
        self.assertIn(self.c.post("/api/products/", body(self.sup, "P-EXTRA"), format="json").status_code, REJECTED)
        self.assertEqual(active_product_count(self.c), LIMIT)

    def test_a_refused_creation_leaves_nothing_behind(self):
        self.c.post("/api/products/", body(self.sup, "P-EXTRA"), format="json")
        self.assertNotIn("Produit P-EXTRA", product_names(self.c))

    def test_only_active_products_count(self):
        self.assertEqual(self.c.patch(f"/api/products/{self.ids[0]}/", {"is_active": False}, format="json").status_code, 200)
        self.assertEqual(self.c.post("/api/products/", body(self.sup, "P-EXTRA"), format="json").status_code, 201)

    def test_reactivating_beyond_the_limit_is_refused(self):
        self.c.patch(f"/api/products/{self.ids[0]}/", {"is_active": False}, format="json")
        self.c.post("/api/products/", body(self.sup, "P-EXTRA"), format="json")  # remplit le créneau libéré
        response = self.c.patch(f"/api/products/{self.ids[0]}/", {"is_active": True}, format="json")
        self.assertIn(response.status_code, REJECTED)
        self.assertEqual(active_product_count(self.c), LIMIT)

    def test_the_limit_is_per_shop(self):
        other = adapter.create_shop("Autre boutique", "someone")
        c2 = adapter.client("someone", other)
        sup2 = make_supplier(c2, "Fournisseur")
        self.assertEqual(c2.post("/api/products/", body(sup2, "P-1"), format="json").status_code, 201)

    def test_the_pro_plan_lifts_the_limit(self):
        adapter.set_plan(self.shop, "pro")
        self.assertEqual(self.c.post("/api/products/", body(self.sup, "P-EXTRA"), format="json").status_code, 201)

    def test_downgrading_never_deletes_data(self):
        adapter.set_plan(self.shop, "pro")
        for i in range(3):
            make_product(self.c, self.sup, f"Q-{i}")
        adapter.set_plan(self.shop, "free")
        self.assertEqual(active_product_count(self.c), LIMIT + 3)  # tout reste lisible
        self.assertIn(self.c.post("/api/products/", body(self.sup, "P-EXTRA"), format="json").status_code, REJECTED)

    def test_member_limit(self):
        for i in range(adapter.FREE_MAX_MEMBERS - 1):  # le propriétaire occupe déjà une place
            adapter.add_member(self.shop, f"membre{i}", "seller")
        with self.assertRaises(adapter.QuotaExceeded):
            adapter.add_member(self.shop, "de-trop", "seller")
        adapter.set_plan(self.shop, "pro")
        adapter.add_member(self.shop, "de-trop", "seller")
