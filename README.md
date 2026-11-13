# Gestion de stock boutique

Application web de gestion de stock pour une boutique, organisée en deux parties : API Django/SQLite dans `backend/` et interface React + TypeScript/Vite dans `frontend/`.

## Fonctionnalités

- Catalogue produits avec fournisseur, référence, prix d’achat et de vente, quantité et seuil d’alerte.
- Ajout et modification de fiches produit.
- Entrées de stock et ventes consignées dans un historique de mouvements.
- Refus d’une vente qui excède la quantité disponible.
- Désactivation/réactivation des produits; une fiche ayant des mouvements n’est pas supprimable afin de préserver l’historique.
- Interface sombre et adaptable aux petits écrans.
- Tableau de bord : ventes et bénéfice du jour, valeur du stock, graphique des 7 derniers jours, meilleures ventes, produits à réapprovisionner (`GET /api/dashboard/`).
- Historique des mouvements paginé et filtrable par type, produit, fournisseur, période et texte libre (`GET /api/movements/?movement_type=sale&date_from=2026-01-01&q=riz`).
- Connexion obligatoire : les comptes se créent avec `python manage.py createsuperuser` ou dans l’administration Django.

## Documentation visuelle

Le dossier [`docs/`](docs/) contient une description du fonctionnement, des diagrammes d’architecture et des parcours de vente/entrée de stock, ainsi qu’un aperçu du modèle de données.

## Prérequis

- Python 3.12+ (Django et ses dépendances dans `backend/requirements.txt`)
- Node.js et npm

## Lancer en développement

Dans un premier terminal PowerShell :

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
$env:DJANGO_SECRET_KEY = 'cle-locale-aleatoire-a-remplacer'
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Dans un second terminal :

```powershell
cd frontend
npm install
npm run dev
```

Interface : http://localhost:5173/  
Administration : http://127.0.0.1:8000/admin/  
API : http://127.0.0.1:8000/api/

Le fichier `.env.example` est un modèle sans secret réel. La base SQLite, les fichiers `.env`, les environnements virtuels, `node_modules` et les builds sont exclus du dépôt. Le compte administrateur et les données de démonstration doivent être créés localement avec les commandes Django, pas partagés dans Git.

## Sécurité et état

Ce projet est un prototype de développement. Toute l’API exige une connexion par jeton (sauf `/api/auth/login/`, limitée à 5 tentatives par minute), mais n’expose pas ce backend à Internet avant d’avoir mis en place les permissions par rôle et la configuration de production (`DEBUG=False`, clé secrète dédiée, hôtes autorisés, HTTPS) et sauvegardes. SQLite convient au développement local; évalue PostgreSQL pour une utilisation concurrente en production.

Aucune licence n’est incluse pour l’instant. Ajoute-en une uniquement après avoir choisi les conditions de réutilisation du code.
