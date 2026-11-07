from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()
PASSWORD = "mot-de-passe-de-test-123"


class AuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gerant", password=PASSWORD, first_name="Awa", is_staff=True)

    def login(self, **overrides):
        return self.client.post("/api/auth/login/", {"username": "gerant", "password": PASSWORD, **overrides},
                                content_type="application/json")

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_login_returns_token_and_user_without_secrets(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["token"])
        self.assertEqual(body["user"], {"id": self.user.id, "username": "gerant", "first_name": "Awa",
                                        "last_name": "", "is_staff": True})

    def test_login_twice_reuses_the_same_token(self):
        self.assertEqual(self.login().json()["token"], self.login().json()["token"])

    def test_wrong_password_and_unknown_user_get_the_same_error(self):
        wrong = self.login(password="faux")
        unknown = self.login(username="inconnu")
        self.assertEqual((wrong.status_code, unknown.status_code), (400, 400))
        self.assertEqual(wrong.json(), unknown.json())

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login().status_code, 400)

    def test_missing_fields_are_reported(self):
        response = self.client.post("/api/auth/login/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"username", "password"})

    def test_me_requires_a_token(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_me_returns_the_user_of_the_token(self):
        token = self.login().json()["token"]
        response = self.client.get("/api/auth/me/", **self.auth(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "gerant")

    def test_logout_invalidates_the_token(self):
        token = self.login().json()["token"]
        self.assertEqual(self.client.post("/api/auth/logout/", **self.auth(token)).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/", **self.auth(token)).status_code, 401)

    def test_logout_requires_a_token(self):
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 401)

    def test_existing_routes_stay_public(self):
        self.assertEqual(self.client.get("/api/products/").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 200)

    def test_invalid_token_is_rejected_even_on_public_routes(self):
        self.assertEqual(self.client.get("/api/products/", **self.auth("jeton-invalide")).status_code, 401)
        token = self.login().json()["token"]
        self.assertEqual(self.client.get("/api/products/", **self.auth(token)).status_code, 200)
