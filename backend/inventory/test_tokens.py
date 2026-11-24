from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .models import Membership, Shop, ShopToken

User = get_user_model()
PASSWORD = "mot-de-passe-de-test-123"


class ShopTokenTests(TestCase):
    """Connexion en deux temps et jetons à durée fixe de 12 h (décision D2)."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("awa", password=PASSWORD)
        self.shop_a = Shop.objects.create(name="Boutique A")
        self.shop_b = Shop.objects.create(name="Boutique B")
        self.foreign = Shop.objects.create(name="Boutique étrangère")
        Membership.objects.create(user=self.user, shop=self.shop_a, role=Membership.Role.MANAGER)
        Membership.objects.create(user=self.user, shop=self.shop_b, role=Membership.Role.SELLER)

    def login(self):
        response = self.client.post("/api/auth/login/", {"username": "awa", "password": PASSWORD},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["token"]

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def shop_token(self, account_token, shop_id):
        return self.client.post("/api/auth/shop-token/", {"shop": shop_id}, content_type="application/json",
                                **self.auth(account_token))

    def age(self, hours):
        return timezone.now() - timedelta(hours=hours)

    # --- choix de la boutique
    def test_my_shops_lists_only_my_shops_with_my_role_in_each(self):
        shops = self.client.get("/api/auth/shops/", **self.auth(self.login())).json()
        self.assertEqual([(s["name"], s["role"]) for s in shops], [("Boutique A", "manager"), ("Boutique B", "seller")])

    def test_a_member_gets_a_token_for_the_chosen_shop(self):
        response = self.shop_token(self.login(), self.shop_b.id)
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["shop"], {"id": self.shop_b.id, "name": "Boutique B", "plan": "free", "role": "seller"})
        token = ShopToken.objects.get(key=body["token"])
        self.assertEqual((token.user, token.shop), (self.user, self.shop_b))

    def test_a_foreign_shop_looks_exactly_like_a_missing_one(self):
        account = self.login()
        foreign = self.shop_token(account, self.foreign.id)
        missing = self.shop_token(account, self.foreign.id + 1000)
        self.assertEqual((foreign.status_code, missing.status_code), (404, 404))
        self.assertEqual(foreign.content, missing.content)
        self.assertFalse(ShopToken.objects.filter(shop=self.foreign).exists())

    def test_the_shop_must_be_given_as_a_number(self):
        account = self.login()
        self.assertEqual(self.shop_token(account, "abc").status_code, 400)
        self.assertEqual(self.client.post("/api/auth/shop-token/", {}, content_type="application/json",
                                          **self.auth(account)).status_code, 400)

    def test_choosing_a_shop_requires_being_logged_in(self):
        self.assertEqual(self.shop_token("jeton-inconnu", self.shop_a.id).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/shops/").status_code, 401)

    def test_a_shop_token_identifies_the_user(self):
        shop_token = self.shop_token(self.login(), self.shop_a.id).json()["token"]
        self.assertEqual(self.client.get("/api/auth/me/", **self.auth(shop_token)).json()["username"], "awa")

    def test_each_use_of_a_shop_token_is_recorded(self):
        shop_token = self.shop_token(self.login(), self.shop_a.id).json()["token"]
        self.assertIsNone(ShopToken.objects.get(key=shop_token).last_used_at)
        self.client.get("/api/auth/me/", **self.auth(shop_token))
        self.assertIsNotNone(ShopToken.objects.get(key=shop_token).last_used_at)

    # --- expiration à durée fixe
    def test_a_shop_token_expires_12_hours_after_creation_even_if_used(self):
        shop_token = self.shop_token(self.login(), self.shop_a.id).json()["token"]
        ShopToken.objects.filter(key=shop_token).update(created_at=self.age(12), last_used_at=timezone.now())
        response = self.client.get("/api/auth/me/", **self.auth(shop_token))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Votre session a expiré. Veuillez vous reconnecter.")
        self.assertFalse(ShopToken.objects.filter(key=shop_token).exists())

    def test_a_shop_token_is_still_valid_just_before_12_hours(self):
        shop_token = self.shop_token(self.login(), self.shop_a.id).json()["token"]
        ShopToken.objects.filter(key=shop_token).update(created_at=self.age(11.9))
        self.assertEqual(self.client.get("/api/auth/me/", **self.auth(shop_token)).status_code, 200)

    def test_the_account_token_also_expires_after_12_hours(self):
        account = self.login()
        Token.objects.filter(key=account).update(created=self.age(12))
        self.assertEqual(self.client.get("/api/auth/me/", **self.auth(account)).status_code, 401)
        self.assertFalse(Token.objects.filter(key=account).exists())

    def test_logging_in_again_after_expiry_gives_a_new_account_token(self):
        old = self.login()
        Token.objects.filter(key=old).update(created=self.age(13))
        new = self.login()
        self.assertNotEqual(old, new)
        self.assertEqual(self.client.get("/api/auth/me/", **self.auth(new)).status_code, 200)

    # --- déconnexion
    def test_logout_cuts_everything(self):
        account = self.login()
        token_a = self.shop_token(account, self.shop_a.id).json()["token"]
        token_b = self.shop_token(account, self.shop_b.id).json()["token"]
        self.assertEqual(self.client.post("/api/auth/logout/", **self.auth(token_a)).status_code, 204)
        for token in (account, token_a, token_b):
            self.assertEqual(self.client.get("/api/auth/me/", **self.auth(token)).status_code, 401)
        self.assertFalse(ShopToken.objects.filter(user=self.user).exists())
