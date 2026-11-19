from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from .models import Membership, Product, Shop, ShopToken, Supplier
from .quotas import create_shop

User = get_user_model()
PASSWORD = "Un-mot-de-passe-solide-42"


class SignupTests(TestCase):
    """Inscription avec création de boutique (décision D6)."""

    def setUp(self):
        cache.clear()  # le compteur d'inscriptions ne doit pas passer d'un test à l'autre

    def signup(self, **overrides):
        body = {"username": "awa", "password": PASSWORD, "first_name": "Awa", "last_name": "Diallo",
                "shop_name": "Chez Awa", **overrides}
        return self.client.post("/api/auth/signup/", body, content_type="application/json")

    def test_signup_creates_the_account_and_its_shop_and_logs_in(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["user"]["first_name"], "Awa")
        self.assertIsNone(body["user"]["role"])  # pas encore de boutique choisie
        shop = Shop.objects.get(name="Chez Awa")
        self.assertEqual(body["shop"], {"id": shop.id, "name": "Chez Awa", "plan": "free", "role": "manager"})
        # Connecté directement (A1) : le jeton compte permet de choisir la boutique.
        shops = self.client.get("/api/auth/shops/", HTTP_AUTHORIZATION=f"Token {body['token']}").json()
        self.assertEqual([s["name"] for s in shops], ["Chez Awa"])
        self.assertTrue(User.objects.get(username="awa").check_password(PASSWORD))

    def test_django_password_rules_apply_in_french(self):
        response = self.signup(password="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Ce mot de passe est trop courant.", response.json()["password"])
        self.assertFalse(User.objects.filter(username="awa").exists())
        self.assertFalse(Shop.objects.exists())

    def test_a_password_too_close_to_the_username_is_refused(self):
        self.assertEqual(self.signup(username="boutiquier", password="boutiquier1").status_code, 400)

    def test_taken_username_and_shop_name_are_refused_whatever_the_case(self):
        self.assertEqual(self.signup().status_code, 201)
        taken_user = self.signup(username="AWA", shop_name="Autre")
        self.assertEqual(taken_user.json()["username"], ["Ce nom d'utilisateur est déjà pris."])
        taken_shop = self.signup(username="jean", shop_name="CHEZ AWA")
        self.assertEqual(taken_shop.json()["shop_name"], ["Une boutique porte déjà ce nom."])
        self.assertEqual((User.objects.count(), Shop.objects.count()), (1, 1))

    def test_required_fields_are_reported(self):
        response = self.client.post("/api/auth/signup/", {}, content_type="application/json")
        self.assertEqual(set(response.json()), {"username", "password", "first_name", "shop_name"})
        self.assertEqual(self.signup(last_name="").status_code, 201)  # le nom de famille est facultatif

    def test_an_old_token_does_not_block_signup(self):
        response = self.client.post("/api/auth/signup/", {"username": "awa", "password": PASSWORD, "first_name": "Awa",
                                                           "shop_name": "Chez Awa"},
                                    content_type="application/json", HTTP_AUTHORIZATION="Token jeton-perime")
        self.assertEqual(response.status_code, 201)

    def test_signups_are_limited_to_5_per_hour_and_per_address(self):
        for n in range(5):
            self.assertEqual(self.signup(username=f"user{n}", shop_name=f"Boutique {n}").status_code, 201)
        blocked = self.signup(username="user5", shop_name="Boutique 5")
        self.assertEqual(blocked.status_code, 429)
        self.assertRegex(blocked.json()["detail"],
                         r"^Trop d'inscriptions depuis cette adresse\. Réessayez dans \d+ minutes?\.$")
        self.assertFalse(User.objects.filter(username="user5").exists())


class CreateAnotherShopTests(TestCase):
    """Une boutique de plus, réservée à une personne déjà gérante (décision D6, B1 restreint)."""

    def setUp(self):
        self.manager = User.objects.create_user("gerant")
        self.first = create_shop("Première", self.manager)
        self.seller = User.objects.create_user("vendeur")
        Membership.objects.create(user=self.seller, shop=self.first, role=Membership.Role.SELLER)
        self.nobody = User.objects.create_user("personne")

    def create(self, user, name="Deuxième"):
        token = ShopToken.objects.create(user=user, shop=self.first).key
        return self.client.post("/api/auth/shops/", {"name": name}, content_type="application/json",
                                HTTP_AUTHORIZATION=f"Token {token}")

    def test_a_manager_can_create_another_shop_and_manages_it(self):
        response = self.create(self.manager)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()["name"], response.json()["role"], response.json()["plan"]),
                         ("Deuxième", "manager", "free"))
        self.assertEqual(self.manager.memberships.count(), 2)

    def test_a_seller_cannot_create_a_shop(self):
        response = self.create(self.seller)
        self.assertEqual((response.status_code, response.json()["detail"]),
                         (403, "Seul un gérant peut créer une autre boutique."))
        self.assertFalse(Shop.objects.filter(name="Deuxième").exists())

    def test_someone_without_any_shop_cannot_create_one_this_way(self):
        self.assertEqual(self.create(self.nobody).status_code, 403)

    def test_the_new_shop_name_must_be_free(self):
        self.assertEqual(self.create(self.manager, name="PREMIÈRE").json()["name"], ["Une boutique porte déjà ce nom."])


class ShopInfoTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("gerant")
        self.shop = create_shop("Boutique", self.manager)
        self.seller = User.objects.create_user("vendeur")
        Membership.objects.create(user=self.seller, shop=self.shop, role=Membership.Role.SELLER)
        supplier = Supplier.objects.create(shop=self.shop, name="F")
        for i, active in enumerate((True, True, False)):
            Product.objects.create(shop=self.shop, name=f"P{i}", reference=f"P{i}", supplier=supplier,
                                   purchase_price=1, selling_price=2, is_active=active)

    def info(self, user):
        token = ShopToken.objects.create(user=user, shop=self.shop).key
        return self.client.get("/api/shop/", HTTP_AUTHORIZATION=f"Token {token}")

    def test_members_see_the_plan_its_limits_and_the_usage(self):
        for user, role in ((self.manager, "manager"), (self.seller, "seller")):
            response = self.info(user)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"id": self.shop.id, "name": "Boutique", "plan": "free",
                                               "plan_label": "gratuit", "role": role,
                                               "limits": {"products": 20, "members": 2},
                                               "usage": {"products": 2, "members": 2}})

    def test_the_account_token_must_choose_a_shop_first(self):
        account = self.client.post("/api/auth/login/", {}, content_type="application/json")  # garde le format
        self.assertEqual(account.status_code, 400)
        from rest_framework.authtoken.models import Token
        token = Token.objects.create(user=self.manager).key
        self.assertEqual(self.client.get("/api/shop/", HTTP_AUTHORIZATION=f"Token {token}").status_code, 403)
