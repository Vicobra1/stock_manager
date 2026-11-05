from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Product, StockMovement, Supplier


def make_product(supplier, reference, quantity=10, purchase="100", selling="150", threshold=5, **extra):
    return Product.objects.create(name=f"Produit {reference}", reference=reference, supplier=supplier,
                                  purchase_price=Decimal(purchase), selling_price=Decimal(selling),
                                  quantity=quantity, low_stock_threshold=threshold, **extra)


def make_movement(product, movement_type, quantity, days_ago=0, unit_price=None, note=""):
    """created_at est auto_now_add : on le réécrit après coup pour simuler le passé."""
    movement = StockMovement.objects.create(product=product, movement_type=movement_type,
                                            quantity=quantity, unit_price=unit_price, note=note)
    StockMovement.objects.filter(pk=movement.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    return movement


class MovementFilterTests(TestCase):
    def setUp(self):
        self.s1 = Supplier.objects.create(name="Fournisseur A")
        self.s2 = Supplier.objects.create(name="Fournisseur B")
        self.p1 = make_product(self.s1, "A-001")
        self.p2 = make_product(self.s2, "B-001")
        self.old_entry = make_movement(self.p1, "entry", 5, days_ago=10, note="Réassort")
        self.sale1 = make_movement(self.p1, "sale", 2, days_ago=1, unit_price="150")
        self.sale2 = make_movement(self.p2, "sale", 1, days_ago=0, unit_price="150")

    def ids(self, **params):
        response = self.client.get("/api/movements/", params)
        self.assertEqual(response.status_code, 200, response.content)
        return {row["id"] for row in response.json()["results"]}

    def test_without_filter_returns_everything_paginated(self):
        response = self.client.get("/api/movements/").json()
        self.assertEqual(response["count"], 3)
        self.assertEqual(response["results"][0]["id"], self.sale2.id)  # le plus récent d'abord

    def test_pagination(self):
        response = self.client.get("/api/movements/", {"limit": 2}).json()
        self.assertEqual((response["count"], len(response["results"])), (3, 2))

    def test_filter_by_type(self):
        self.assertEqual(self.ids(movement_type="sale"), {self.sale1.id, self.sale2.id})

    def test_filter_by_product_and_supplier(self):
        self.assertEqual(self.ids(product=self.p2.id), {self.sale2.id})
        self.assertEqual(self.ids(supplier=self.s1.id), {self.old_entry.id, self.sale1.id})

    def test_filter_by_dates_inclusive(self):
        today = timezone.localdate()
        self.assertEqual(self.ids(date_from=(today - timedelta(days=1)).isoformat()), {self.sale1.id, self.sale2.id})
        self.assertEqual(self.ids(date_to=(today - timedelta(days=5)).isoformat()), {self.old_entry.id})
        self.assertEqual(self.ids(date_from=today.isoformat(), date_to=today.isoformat()), {self.sale2.id})

    def test_search_in_product_and_note(self):
        self.assertEqual(self.ids(q="B-001"), {self.sale2.id})
        self.assertEqual(self.ids(q="réassort"), {self.old_entry.id})

    def test_filters_combine(self):
        self.assertEqual(self.ids(supplier=self.s1.id, movement_type="sale"), {self.sale1.id})

    def test_invalid_parameters_are_rejected(self):
        for params in ({"movement_type": "nimporte"}, {"date_from": "hier"}, {"product": "abc"},
                       {"date_from": "2026-02-01", "date_to": "2026-01-01"}):
            self.assertEqual(self.client.get("/api/movements/", params).status_code, 400, params)


class DashboardTests(TestCase):
    def setUp(self):
        supplier = Supplier.objects.create(name="Fournisseur A")
        self.ok = make_product(supplier, "OK", quantity=10, purchase="100", selling="150")
        self.low = make_product(supplier, "LOW", quantity=2, purchase="50", selling="80")
        self.empty = make_product(supplier, "ZERO", quantity=0, purchase="10", selling="20")
        make_product(supplier, "OFF", quantity=99, is_active=False)
        make_movement(self.ok, "sale", 3, days_ago=0, unit_price="150")
        make_movement(self.ok, "sale", 1, days_ago=2, unit_price="150")
        make_movement(self.low, "sale", 1, days_ago=40, unit_price="80")
        make_movement(self.ok, "entry", 20, days_ago=0)

    def data(self):
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_product_counters_ignore_inactive(self):
        self.assertEqual(self.data()["products"], {"active": 3, "low_stock": 2, "out_of_stock": 1})

    def test_stock_value(self):
        value = self.data()["stock_value"]
        self.assertEqual(Decimal(value["at_cost"]), Decimal("10") * 100 + 2 * 50)
        self.assertEqual(Decimal(value["at_retail"]), Decimal("10") * 150 + 2 * 80)

    def test_today_counts_only_sales_of_today(self):
        today = self.data()["today"]
        self.assertEqual((Decimal(today["revenue"]), Decimal(today["profit"]), today["units"]),
                         (Decimal("450"), Decimal("150"), 3))

    def test_last_7_days_is_complete_and_ordered(self):
        days = self.data()["last_7_days"]
        self.assertEqual(len(days), 7)
        self.assertEqual(days[-1]["date"], timezone.localdate().isoformat())
        self.assertEqual(days[-1]["units"], 3)
        self.assertEqual(days[-3]["units"], 1)
        self.assertEqual(days[0]["units"], 0)

    def test_low_stock_list_and_top_products(self):
        data = self.data()
        self.assertEqual([p["reference"] for p in data["low_stock_products"]], ["ZERO", "LOW"])
        self.assertEqual([p["reference"] for p in data["top_products"]], ["OK"])  # la vente LOW date de 40 jours
        self.assertEqual(data["top_products"][0]["units"], 4)

    def test_empty_database(self):
        StockMovement.objects.all().delete()
        Product.objects.all().delete()
        data = self.data()
        self.assertEqual(data["products"]["active"], 0)
        self.assertEqual(Decimal(data["stock_value"]["at_cost"]), 0)
        self.assertEqual(data["recent_movements"], [])
