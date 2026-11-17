"""Utilitaires des tests d'acceptation : tout passe par l'API publique, jamais par la base."""
import unittest

from . import adapter

requires_adapter = unittest.skipUnless(adapter.IMPLEMENTED, "adapter.IMPLEMENTED est False : adaptateur non rempli")

REJECTED = (400, 402, 403, 409)  # statuts acceptés pour « refusé pour raison de quota ou de validation »
HIDDEN = (403, 404)  # statuts acceptés pour « tu n'as pas à savoir que ça existe / tu n'y as pas droit »


def rows(response):
    """Les lignes d'une réponse liste, paginée ou non."""
    data = response.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


def make_supplier(c, name):
    response = c.post("/api/suppliers/", {"name": name}, format="json")
    assert response.status_code == 201, (response.status_code, response.content)
    return response.json()["id"]


def make_product(c, supplier_id, reference, name=None, quantity=0, purchase=100, selling=150, **extra):
    body = {"name": name or f"Produit {reference}", "reference": reference, "supplier": supplier_id,
            "purchase_price": purchase, "selling_price": selling, "initial_quantity": quantity, **extra}
    response = c.post("/api/products/", body, format="json")
    assert response.status_code == 201, (response.status_code, response.content)
    return response.json()["id"]


def sell(c, product_id, quantity=1):
    response = c.post(f"/api/products/{product_id}/sale/", {"quantity": quantity}, format="json")
    assert response.status_code == 201, (response.status_code, response.content)
    return response.json()


def movement_ids(c):
    response = c.get("/api/movements/", {"limit": 200})
    assert response.status_code == 200, response.content
    return {m["id"] for m in rows(response)}


def product_names(c):
    response = c.get("/api/products/")
    assert response.status_code == 200, response.content
    return {p["name"] for p in rows(response)}


def active_product_count(c):
    response = c.get("/api/products/", {"active": "true"})
    assert response.status_code == 200, response.content
    return len(rows(response))
