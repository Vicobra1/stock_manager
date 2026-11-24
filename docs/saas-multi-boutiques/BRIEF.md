# Cahier des charges : version multi-boutiques (SaaS)

## 1. Contexte

StockBoutique sert aujourd'hui **une seule boutique** : tous les utilisateurs partagent les mêmes produits,
fournisseurs et mouvements. L'objectif est de proposer l'application comme **un service utilisé par plusieurs boutiques
indépendantes**, sur une même installation, sans qu'aucune puisse voir ou modifier les données d'une autre.

Ce document décrit le besoin et les contraintes. **Il ne fixe pas la solution technique** : le choix de l'architecture
fait partie du travail et doit être documenté (voir section 5).

## 2. Exigences fonctionnelles

1. **Plusieurs boutiques** cohabitent. Chacune a ses produits, fournisseurs, mouvements et son tableau de bord.
2. **Plusieurs utilisateurs par boutique**, et **un utilisateur peut appartenir à plusieurs boutiques**, avec un rôle
   différent dans chacune (gérant dans l'une, vendeur dans l'autre). Les rôles actuels (gérant, vendeur) et leurs droits
   restent ceux d'aujourd'hui, mais s'appliquent **dans le cadre d'une boutique**.
3. **Deux plans** par boutique :

   | | Gratuit | Pro |
   |---|---|---|
   | Produits **actifs** | 20 | 1 000 |
   | Membres (propriétaire compris) | 2 | 50 |

   - Désactiver un produit libère une place ; en réactiver un en redemande une.
   - Passer de Pro à Gratuit **ne supprime aucune donnée** : tout reste lisible, seules les nouvelles créations sont
     refusées si la limite est dépassée.
4. **Reprise de l'existant** : la boutique actuelle, ses utilisateurs, ses produits et son historique sont conservés
   lors de la migration, et chaque utilisateur garde son rôle.
5. **Interface** *(seconde phase, après le backend)* : inscription avec création de boutique, choix et changement de
   boutique, affichage du plan et des limites atteintes.

## 3. Contraintes

- Les valeurs aujourd'hui **uniques** (référence produit, nom de fournisseur) ne le sont qu'**au sein d'une boutique**.
- Aucun client ne doit pouvoir, même en construisant des requêtes malveillantes, lire, modifier ou **deviner l'existence**
  d'une donnée d'une autre boutique.
- Des requêtes simultanées ne doivent jamais permettre de dépasser un quota.
- L'API existante reste compatible (URLs, formats de réponse, codes d'erreur) : le frontend actuel doit continuer à
  fonctionner une fois la boutique choisie.
- La base actuelle est SQLite, mais la conception ne doit pas s'y enfermer : indiquer ce qui changerait avec PostgreSQL.

## 4. Livrables

1. Le code, sur une branche, via une pull request.
2. Les **décisions de conception** consignées (voir section 5).
3. L'adaptateur des tests d'acceptation rempli, et ces tests au vert (voir section 6).
4. Une démonstration sur une copie de la base actuelle : migration, vérification que données et rôles existants sont
   intacts, création d'une seconde boutique, vérification de l'isolation.

## 5. Décisions de conception à documenter

Chaque décision structurante fait l'objet d'un court document dans `docs/saas-multi-boutiques/adr/` (modèle :
`0000-modele.md`), avec au moins deux options comparées et la justification du choix. Points à couvrir :

- l'isolation des données entre boutiques, et l'endroit où elle est garantie ;
- la façon dont l'API identifie la boutique concernée par une requête ;
- l'emplacement du rôle d'un utilisateur et la prise en compte d'un changement de rôle ;
- le comptage et l'application des quotas ;
- la migration des données existantes et le retour arrière ;
- la protection contre l'oubli du filtrage par boutique dans une future vue.

## 6. Critères d'acceptation

**Tests d'acceptation.** Le dossier `backend/saas_acceptance/` contient des tests indépendants de l'architecture : ils
interrogent l'API comme un vrai client (isolation, rôles par boutique, quotas, concurrence). Seul `adapter.py` les relie
à l'implémentation (création de boutique, ajout de membre, changement de plan, client authentifié pour une boutique) ;
il est documenté dans le fichier.

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py test saas_acceptance   # ignorés tant que IMPLEMENTED vaut False
.\.venv\Scripts\python.exe manage.py test                   # suite complète
```

- Les fichiers `test_*.py` et `support.py` de ce dossier ne sont pas modifiés ; une divergence se discute et se consigne.
- Les 46 tests existants restent au vert ; toute adaptation est justifiée.
- Ces tests vérifient des comportements, ils ne remplacent pas la justification de la conception.

**Migration.** Sur une copie de la base actuelle, la migration se déroule sans perte, est réversible, et les rôles
existants sont conservés.

## 7. Usage d'un assistant IA

L'usage d'une IA est autorisé. Chaque décision et chaque ligne livrée restent sous la responsabilité de leur auteur, qui
doit pouvoir les expliquer. Les documents de décision sont rédigés par l'auteur ; ils mentionnent les propositions d'un
assistant qui n'ont pas été retenues, et pourquoi.

## 8. Hors périmètre

Facturation et paiement réels, envoi d'e-mails d'invitation, interface d'administration de la plateforme, passage effectif
à PostgreSQL.
