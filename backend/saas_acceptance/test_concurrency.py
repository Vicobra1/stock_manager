import threading

from django.db import connection
from django.test import TransactionTestCase

from . import adapter
from .support import REJECTED, active_product_count, make_product, make_supplier, requires_adapter

LIMIT = adapter.FREE_MAX_PRODUCTS
THREADS = 8


@requires_adapter
class QuotaConcurrencyTests(TransactionTestCase):
    """Plusieurs créations simultanées quand il ne reste qu'une place : une seule doit réussir."""

    def test_parallel_creations_never_exceed_the_limit(self):
        shop = adapter.create_shop("Boutique", "owner")
        owner = adapter.client("owner", shop)
        sup = make_supplier(owner, "Fournisseur")
        for i in range(LIMIT - 1):
            make_product(owner, sup, f"P-{i}")

        statuses, barrier = [], threading.Barrier(THREADS)

        def create(n):
            try:
                c = adapter.client("owner", shop)
                body = {"name": f"Concurrent {n}", "reference": f"C-{n}", "supplier": sup,
                        "purchase_price": 1, "selling_price": 2}
                barrier.wait(timeout=10)
                statuses.append(c.post("/api/products/", body, format="json").status_code)
            except Exception as exc:  # une erreur serveur (verrou de base...) est un échec, pas un refus
                statuses.append(repr(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=create, args=(n,)) for n in range(THREADS)]
        [t.start() for t in threads]
        [t.join(timeout=30) for t in threads]

        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertTrue(all(s in REJECTED for s in statuses if s != 201), statuses)
        self.assertEqual(active_product_count(owner), LIMIT)
