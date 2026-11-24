from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Membership, Shop
from .quotas import create_shop

User = get_user_model()


class ShopAdminTests(TestCase):
    """Boutiques et membres dans l'admin Django : mêmes règles que l'API (nom unique, limite de membres)."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="x")
        self.client.force_login(self.admin)
        self.owner = User.objects.create_user("gerant")
        self.seller = User.objects.create_user("vendeur")
        self.extra = User.objects.create_user("troisieme")
        self.shop = create_shop("Première", self.owner)

    def shop_form(self, plan, users, name="Première"):
        """Données du formulaire de modification de la boutique, avec ses membres (inline)."""
        existing = list(self.shop.memberships.order_by("pk"))
        data = {"name": name, "plan": plan, "memberships-TOTAL_FORMS": str(len(users)),
                "memberships-INITIAL_FORMS": str(len(existing)), "memberships-MIN_NUM_FORMS": "0",
                "memberships-MAX_NUM_FORMS": "1000"}
        for i, (user, role) in enumerate(users):
            data.update({f"memberships-{i}-user": user.pk, f"memberships-{i}-role": role,
                         f"memberships-{i}-shop": self.shop.pk})
            if i < len(existing):
                data[f"memberships-{i}-id"] = existing[i].pk
        return self.client.post(f"/admin/inventory/shop/{self.shop.pk}/change/", data)

    def test_the_lists_open(self):
        for url in ("/admin/inventory/shop/", "/admin/inventory/membership/", "/admin/inventory/shop/add/",
                    f"/admin/inventory/shop/{self.shop.pk}/change/", "/admin/inventory/membership/add/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/admin/inventory/shop/"), "1 / 2")  # membres / limite

    def test_members_are_added_within_the_plan_limit(self):
        response = self.shop_form("free", [(self.owner, "manager"), (self.seller, "seller")])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.shop.memberships.count(), 2)

        refused = self.shop_form("free", [(self.owner, "manager"), (self.seller, "seller"), (self.extra, "seller")])
        self.assertContains(refused, "Limite du plan gratuit atteinte : 2 membres.")
        self.assertEqual(self.shop.memberships.count(), 2)

    def test_switching_to_pro_in_the_same_form_allows_more_members(self):
        Membership.objects.create(shop=self.shop, user=self.seller, role="seller")
        response = self.shop_form("pro", [(self.owner, "manager"), (self.seller, "seller"), (self.extra, "seller")])
        self.assertEqual(response.status_code, 302)
        self.shop.refresh_from_db()
        self.assertEqual((self.shop.plan, self.shop.memberships.count()), ("pro", 3))

    def test_back_to_free_keeps_every_member(self):
        self.shop.plan = "pro"; self.shop.save()
        for user in (self.seller, self.extra):
            Membership.objects.create(shop=self.shop, user=user, role="seller")
        # Repasser en gratuit avec 3 membres sur 2 : accepté, personne n'est retiré.
        users = [(self.owner, "manager"), (self.seller, "seller"), (self.extra, "seller")]
        self.assertEqual(self.shop_form("free", users).status_code, 302)
        self.shop.refresh_from_db()
        self.assertEqual((self.shop.plan, self.shop.memberships.count()), ("free", 3))
        # Mais aucun membre de plus.
        fourth = User.objects.create_user("quatrieme")
        self.assertContains(self.shop_form("free", users + [(fourth, "seller")]), "Limite du plan gratuit atteinte")
        self.assertEqual(self.shop.memberships.count(), 3)

    def test_the_membership_page_applies_the_limit_too(self):
        url = "/admin/inventory/membership/add/"
        self.assertEqual(self.client.post(url, {"user": self.seller.pk, "shop": self.shop.pk, "role": "seller"})
                         .status_code, 302)
        refused = self.client.post(url, {"user": self.extra.pk, "shop": self.shop.pk, "role": "seller"})
        self.assertContains(refused, "Limite du plan gratuit atteinte : 2 membres.")
        # Changer le rôle d'un membre existant ne demande pas de place.
        member = Membership.objects.get(user=self.seller)
        changed = self.client.post(f"/admin/inventory/membership/{member.pk}/change/",
                                   {"user": self.seller.pk, "shop": self.shop.pk, "role": "manager"})
        self.assertEqual(changed.status_code, 302)
        self.assertEqual(Membership.objects.get(pk=member.pk).role, "manager")

    def test_a_shop_name_already_taken_is_refused_whatever_the_case(self):
        response = self.client.post("/admin/inventory/shop/add/", {
            "name": "PREMIÈRE", "plan": "free", "memberships-TOTAL_FORMS": "0", "memberships-INITIAL_FORMS": "0",
            "memberships-MIN_NUM_FORMS": "0", "memberships-MAX_NUM_FORMS": "1000"})
        self.assertContains(response, "Une boutique porte déjà ce nom.")
        self.assertEqual(Shop.objects.count(), 1)
