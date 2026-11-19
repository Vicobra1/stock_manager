import threading
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase

from .models import Membership, Product, Shop, ShopToken, StockMovement, Supplier
from . import quotas
from .quotas import PLAN_LIMITS, QuotaExceeded, add_member, create_shop, set_plan

User = get_user_model()
FREE_PRODUCTS = PLAN_LIMITS[Shop.Plan.FREE]["products"]


class QuotaHelpers:
    def setup_shop(self):
        self.owner = User.objects.create_user("owner")
        self.shop = create_shop("Boutique", self.owner)
        self.supplier = Supplier.objects.create(shop=self.shop, name="Fournisseur")
        self.token = ShopToken.objects.create(user=self.owner, shop=self.shop).key

    def fill(self, count, active=True):
        for i in range(count):
            Product.objects.create(shop=self.shop, name=f"P{i}-{active}", reference=f"P{i}-{active}",
                                   supplier=self.supplier, purchase_price=1, selling_price=2, is_active=active)

    def create(self, reference, client=None, **extra):
        body = {"name": reference, "reference": reference, "supplier": self.supplier.id,
                "purchase_price": 1, "selling_price": 2, **extra}
        return (client or self.client).post("/api/products/", body, content_type="application/json",
                                            HTTP_AUTHORIZATION=f"Token {self.token}")


class ProductQuotaTests(QuotaHelpers, TestCase):
    def setUp(self):
        self.setup_shop()

    def test_the_free_plan_stops_at_20_active_products_with_a_403(self):
        self.fill(FREE_PRODUCTS - 1)
        self.assertEqual(self.create("DERNIERE").status_code, 201)
        refused = self.create("DE-TROP")
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(refused.json(), {"detail": "Limite du plan gratuit atteinte : 20 produits actifs. "
                                                    "Désactivez un produit ou passez au plan Pro.",
                                          "code": "quota_exceeded"})

    def test_a_quota_refusal_is_distinguishable_from_a_rights_refusal(self):
        self.fill(FREE_PRODUCTS)
        seller = User.objects.create_user("vendeur")
        Membership.objects.create(user=seller, shop=self.shop, role=Membership.Role.SELLER)
        seller_token = ShopToken.objects.create(user=seller, shop=self.shop).key
        rights = self.client.get("/api/dashboard/", HTTP_AUTHORIZATION=f"Token {seller_token}")
        quota = self.create("DE-TROP")
        self.assertEqual((rights.status_code, quota.status_code), (403, 403))
        self.assertNotIn("code", rights.json())
        self.assertEqual(quota.json()["code"], "quota_exceeded")

    def test_messages_can_be_changed_in_one_place(self):
        self.fill(FREE_PRODUCTS)
        with mock.patch.dict(quotas.QUOTA_MESSAGES, {("products", Shop.Plan.FREE): "Plus de place ({limit})."}):
            self.assertEqual(self.create("DE-TROP").json()["detail"], "Plus de place (20).")

    def test_a_refused_creation_leaves_nothing_behind(self):
        self.fill(FREE_PRODUCTS)
        movements = StockMovement.objects.count()
        self.assertEqual(self.create("DE-TROP", initial_quantity=5).status_code, 403)
        self.assertFalse(Product.objects.filter(reference="DE-TROP").exists())
        self.assertEqual(StockMovement.objects.count(), movements)

    def test_inactive_products_do_not_count_and_can_still_be_created(self):
        self.fill(FREE_PRODUCTS)
        self.fill(3, active=False)
        self.assertEqual(self.create("INACTIF", is_active=False).status_code, 201)
        Product.objects.filter(reference="P0-True").update(is_active=False)  # désactiver libère une place
        self.assertEqual(self.create("PLACE-LIBEREE").status_code, 201)

    def test_reactivating_beyond_the_limit_is_refused(self):
        self.fill(FREE_PRODUCTS)
        off = Product.objects.create(shop=self.shop, name="Off", reference="OFF", supplier=self.supplier,
                                     purchase_price=1, selling_price=2, is_active=False)
        response = self.client.patch(f"/api/products/{off.id}/", {"is_active": True}, content_type="application/json",
                                     HTTP_AUTHORIZATION=f"Token {self.token}")
        self.assertEqual(response.status_code, 403)
        off.refresh_from_db()
        self.assertFalse(off.is_active)

    def test_editing_an_active_product_at_the_limit_is_still_allowed(self):
        self.fill(FREE_PRODUCTS)
        product = Product.objects.filter(shop=self.shop).first()
        response = self.client.patch(f"/api/products/{product.id}/", {"selling_price": 3, "is_active": True},
                                     content_type="application/json", HTTP_AUTHORIZATION=f"Token {self.token}")
        self.assertEqual(response.status_code, 200)

    def test_the_pro_plan_lifts_the_limit_and_downgrading_deletes_nothing(self):
        self.fill(FREE_PRODUCTS)
        set_plan(self.shop, Shop.Plan.PRO)
        self.assertEqual(self.create("PRO-1").status_code, 201)
        set_plan(self.shop, Shop.Plan.FREE)
        self.assertEqual(Product.objects.filter(shop=self.shop, is_active=True).count(), FREE_PRODUCTS + 1)
        self.assertEqual(self.create("REFUSE").status_code, 403)
        listing = self.client.get("/api/products/", {"active": "true"}, HTTP_AUTHORIZATION=f"Token {self.token}")
        self.assertEqual(len(listing.json()), FREE_PRODUCTS + 1)

    def test_the_limit_is_per_shop(self):
        self.fill(FREE_PRODUCTS)
        other_owner = User.objects.create_user("other")
        other = create_shop("Autre boutique", other_owner)
        Supplier.objects.create(shop=other, name="Fournisseur")
        token = ShopToken.objects.create(user=other_owner, shop=other).key
        body = {"name": "X", "reference": "X", "supplier": other.suppliers.get().id, "purchase_price": 1,
                "selling_price": 2}
        response = self.client.post("/api/products/", body, content_type="application/json",
                                    HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(response.status_code, 201)


class MemberQuotaTests(TestCase):
    def test_the_owner_counts_and_the_free_plan_stops_at_two_members(self):
        owner = User.objects.create_user("owner")
        shop = create_shop("Boutique", owner)
        self.assertEqual(Membership.objects.get(shop=shop).role, Membership.Role.MANAGER)
        add_member(shop, User.objects.create_user("second"), Membership.Role.SELLER)
        with self.assertRaises(QuotaExceeded):
            add_member(shop, User.objects.create_user("troisieme"), Membership.Role.SELLER)
        self.assertEqual(Membership.objects.filter(shop=shop).count(), 2)
        set_plan(shop, Shop.Plan.PRO)
        add_member(shop, User.objects.create_user("quatrieme"), Membership.Role.SELLER)
        self.assertEqual(Membership.objects.filter(shop=shop).count(), 3)


def slow_slot_check(shop):
    """Comptage normal, puis une pause : élargit la fenêtre entre « je compte » et « je crée ».

    Sans pause, les demandes simultanées ne se chevauchent presque jamais sur une petite machine et le test passerait
    même sans protection. Avec elle, une seconde demande qui ne prendrait pas le « ticket » compterait forcément
    pendant que la première attend : le dépassement deviendrait certain.
    """
    quotas.ensure_product_slot(shop)
    time.sleep(0.2)


class SimultaneousCreationTests(QuotaHelpers, TransactionTestCase):
    """Il reste une place et 8 créations arrivent en même temps : une seule doit passer (option C1)."""

    @mock.patch("inventory.views.ensure_product_slot", side_effect=slow_slot_check)
    def test_parallel_creations_never_exceed_the_limit(self, _slow):
        self.setup_shop()
        self.fill(FREE_PRODUCTS - 1)
        statuses, barrier = [], threading.Barrier(8)

        def create(n):
            try:
                from django.test import Client
                barrier.wait(timeout=10)
                statuses.append(self.create(f"C-{n}", client=Client()).status_code)
            except Exception as exc:  # une erreur (base verrouillée…) est un échec, pas un refus
                statuses.append(repr(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=create, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join(timeout=30) for t in threads]
        self.assertEqual(sorted(statuses, key=str), sorted([201] + [403] * 7, key=str), statuses)
        self.assertEqual(Product.objects.filter(shop=self.shop, is_active=True).count(), FREE_PRODUCTS)
