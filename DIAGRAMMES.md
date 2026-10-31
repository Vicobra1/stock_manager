# Fonctionnement de StockBoutique

Ce document décrit le fonctionnement présent dans le code du projet. Les propositions d’évolution sont indiquées séparément à la fin.

## Illustrations

### Vue d’ensemble de la plateforme

![Illustration de l'interface, de l'API et de la base de données](docs/images/vue-plateforme.svg)

### Vente et entrée de stock

![Illustration des parcours de vente et d'entrée de stock](docs/images/parcours-vente-stock.svg)

## 1. Vue d’ensemble technique

```mermaid
flowchart LR
    U[Utilisateur] --> UI[Interface React + TypeScript\nCatalogue et formulaires]
    UI -->|Requêtes HTTP /api| API[API REST Django REST Framework]
    API --> P[Gestion des produits]
    API --> F[Gestion des fournisseurs]
    API --> M[Gestion des mouvements]
    P --> DB[(Base SQLite)]
    F --> DB
    M --> DB
```

L’interface charge les produits et fournisseurs via l’API. Les mouvements de stock mettent à jour la quantité du produit et ajoutent une ligne d’historique.

## 2. Parcours d’un produit et mouvements de stock

```mermaid
flowchart TD
    A[Commencer] --> B{Action choisie}
    B -->|Créer un produit| C[Saisir nom, référence, fournisseur, prix et seuil]
    C --> D{Stock initial supérieur à 0 ?}
    D -->|Oui| E[Créer le produit et son mouvement « stock initial »]
    D -->|Non| F[Créer le produit avec quantité 0]
    B -->|Entrée de stock| G[Saisir une quantité positive]
    G --> H[Augmenter la quantité disponible]
    H --> I[Enregistrer le mouvement « entrée »]
    B -->|Vente| J[Saisir une quantité positive]
    J --> K{Quantité demandée disponible ?}
    K -->|Non| L[Refuser la vente et afficher le stock disponible]
    K -->|Oui| M[Déduire la quantité vendue]
    M --> N[Enregistrer le mouvement « vente »]
    E --> O[Recalculer l’état du stock]
    F --> O
    I --> O
    N --> O
    O --> P{Quantité ≤ seuil d’alerte ?}
    P -->|Oui| Q[Afficher « Stock faible »]
    P -->|Non| R[Afficher « En stock »]
```

## 3. Modèle des données

```mermaid
erDiagram
    SUPPLIER ||--o{ PRODUCT : fournit
    PRODUCT ||--o{ STOCK_MOVEMENT : concerne

    SUPPLIER {
        int id PK
        string name
        string phone
        string email
        string address
        string notes
    }
    PRODUCT {
        int id PK
        string name
        string reference UK
        int supplier_id FK
        decimal purchase_price
        decimal selling_price
        int quantity
        int low_stock_threshold
        boolean is_active
    }
    STOCK_MOVEMENT {
        int id PK
        int product_id FK
        string movement_type
        int quantity
        decimal unit_price
        string note
        datetime created_at
    }
```

Types de mouvements présents : `initial`, `entry`, `sale` et `adjustment`. Le parcours de création, d’entrée et de vente est implémenté dans l’interface et l’API ; l’ajustement existe dans le modèle de données, mais n’a pas encore d’action dédiée dans l’interface.

## 4. Catalogue et conservation de l’historique

```mermaid
flowchart TD
    A[Produit dans le catalogue] --> B{Possède des mouvements ?}
    B -->|Non| C[Suppression autorisée]
    B -->|Oui| D[Suppression refusée]
    D --> E[Désactiver le produit]
    E --> F[Produit masqué du catalogue actif]
    F --> G[Historique conservé]
    G --> H[Réactivation possible]
```

## 5. Idées d’évolution

1. **Alerte de réapprovisionnement** : afficher les produits sous seuil dans une vue dédiée et proposer une quantité à commander.
2. **Gestion des corrections de stock** : ajouter une action d’ajustement avec motif obligatoire (inventaire, casse, perte, erreur de saisie).
3. **Historique consultable** : ajouter une page avec filtres par produit, type de mouvement et période, ainsi qu’un export CSV.
4. **Indicateurs de vente** : suivre le chiffre d’affaires et la marge à partir des ventes et des prix enregistrés au moment du mouvement.
5. **Sécurité multi-utilisateur** : authentification et rôles (administrateur, vendeur, gestionnaire), avec traçabilité de l’auteur de chaque opération.
6. **Fiabilité en production** : sauvegardes automatiques et base PostgreSQL pour mieux gérer plusieurs utilisateurs simultanés.

Les idées 5 et 6 sont particulièrement importantes avant d’exposer cette API sur Internet : le README précise actuellement que l’API autorise les requêtes sans authentification.
