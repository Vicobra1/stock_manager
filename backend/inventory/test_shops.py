from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Membership, Shop

User = get_user_model()


class ShopModelTests(TestCase):
    def setUp(self):
        self.shop_a = Shop.objects.create(name="Boutique A")
        self.shop_b = Shop.objects.create(name="Boutique B", plan=Shop.Plan.PRO)
        self.user = User.objects.create_user("awa")

    def test_two_shops_cannot_share_a_name_whatever_the_case(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Shop.objects.create(name="boutique a")

    def test_a_new_shop_starts_on_the_free_plan(self):
        self.assertEqual(self.shop_a.plan, Shop.Plan.FREE)

    def test_a_user_can_have_a_different_role_in_each_shop(self):
        Membership.objects.create(user=self.user, shop=self.shop_a, role=Membership.Role.MANAGER)
        Membership.objects.create(user=self.user, shop=self.shop_b, role=Membership.Role.SELLER)
        roles = dict(self.user.memberships.values_list("shop__name", "role"))
        self.assertEqual(roles, {"Boutique A": "manager", "Boutique B": "seller"})

    def test_only_one_role_per_user_and_shop(self):
        Membership.objects.create(user=self.user, shop=self.shop_a, role=Membership.Role.MANAGER)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(user=self.user, shop=self.shop_a, role=Membership.Role.SELLER)

    def test_deleting_a_shop_removes_its_memberships_but_not_the_users(self):
        Membership.objects.create(user=self.user, shop=self.shop_a, role=Membership.Role.MANAGER)
        self.shop_a.delete()
        self.assertFalse(Membership.objects.exists())
        self.assertTrue(User.objects.filter(username="awa").exists())
