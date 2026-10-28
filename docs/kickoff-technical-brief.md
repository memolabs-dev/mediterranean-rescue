# Mediterranean Rescue Atlas — cadrage technique de démarrage

**Statut : proposition indépendante, non validée par SOS MEDITERRANEE / Data for Good.**  
**Responsable de travail :** Tech lead bénévole entrant. **Référence :** issue #42.  
**Réunion de validation :** vendredi 30 octobre 2026, 13 h–14 h (Paris).

## 1. Décision à obtenir en premier

**À quel problème concret le nouvel Atlas doit-il répondre, sachant que SOS dispose déjà d'une carte ?**

- [Carte SOS existante](https://map.sosmediterranee.org/) et [code CartONG](https://github.com/CartONG/SOSMedDashboard) : carte, fiches, filtres et graphiques. L'audit indépendant de la donnée utilisée par cette carte la trouve arrêtée début février 2024.
- [Dépôt Data for Good](https://github.com/dataforgoodfr/mediterranean-rescue) : gabarit Python au moment de la consultation, **pas** la carte CartONG.
- [Notre démonstrateur indépendant](https://github.com/memolabs-dev/mediterranean-rescue) : API, base PostGIS, carte, staging et revue humaine. Ce travail n'est ni un produit adopté ni une décision d'architecture de l'équipe.
- [Audit de reconstruction du journal de bord](backfill-2024-2026.md) : candidats à la remise à jour des opérations, issus de textes publics, avec des cas signalés pour revue. **Ces résultats internes ne valent ni validation par SOS ni autorisation de republication.**

| Option | Première livraison utile | Avantage | Risque / dépendance |
| --- | --- | --- | --- |
| **A — Remettre à jour CartONG** | Export de lignes relues au format `Data_operations` puis chargement par l'équipe éditrice | Effort minimal, carte connue du public | Propriétaire du Sheet, droits, corrections et maintenance à confirmer |
| **B — Moderniser CartONG** | Flux de données gouverné + carte rénovée | Continuité fonctionnelle, meilleure maintenabilité éventuelle | Coût de migration, droits du code et hébergement non confirmés |
| **C — Outil complémentaire** | Espace de revue/traçabilité, export vers la carte actuelle | Répond au travail invisible d'actualisation | Deux applications à maintenir ; risque de doublon |
 
**Recommandation provisoire :** commencer par comparer le flux de données et tester un export relu ; ne choisir ni nouvelle stack ni remplacement avant validation du commanditaire.

## 2. Contrat de donnée minimal à confirmer

L'unité est **une opération documentée**, pas le voyage entier ; un transfert, une évacuation et un débarquement ne représentent pas nécessairement des personnes différentes. Les agrégats ne doivent pas additionner ces catégories sans règle métier.

| Donnée cible | Exemple / règle | Provenance |
| --- | --- | --- |
| `external_id` | Identité stable dans **la même source** ; jamais le seul numéro de ligne | Attribuée ou rapprochée explicitement |
| `source_url` | Lien vers le document à l'origine de l'affirmation | Référence conservée |
| `occurred_on`, `kind` | Date sans heure inventée ; sauvetage / transfert / évacuation / incident | Source vérifiée |
| `people` | Entier **ou null** ; inconnu n'est pas zéro | Chiffre et définition tracés |
| `longitude`, `latitude`, `location_precision` | WGS84, position absente ou accompagnée de sa précision | Ne jamais déduire une position exacte |
| `summary`, `title` | Contexte descriptif, sans fait inventé | Lien vers phrase ou preuve |
| Revue / publication | Brouillon → permission + motif + droits sur la source → public → retrait possible | Acteur, date et motif auditables |

Voir [catalogue de données](data-catalog.md) et [contrat de Sheets](../contracts/sheets-v1.json) : **contrats observés, non validés officiellement**.

## 3. Première recette de données : cinq cas fictifs, aucune opération réelle

Les fixtures [kickoff_synthetic_events.json](../backend/catalog/tests/fixtures/kickoff_synthetic_events.json) contiennent 5 événements **SYNTHETIC** et utilisent exclusivement des URLs `example.org`. Le test [test_kickoff_vertical_slice.py](../backend/catalog/tests/test_kickoff_vertical_slice.py) utilise **les vrais modèles PostGIS, services d'import, décision de publication et endpoints publics**.

Vérifier, avec résultat automatisé et non une simple capture d'écran :

1. Import → staging privé → 5 brouillons, **0 public** ; rejouer le lot ne crée aucun doublon.
2. Publier un événement sans effectif et sans position → valeur `null`, fiche visible, **aucun point inventé**.
3. Refuser la publication par un utilisateur non habilité ou sans accord de publication de la source.
4. Refuser un conflit d'identité ou une coordonnée incomplète ; rejeter toute réimportation qui écraserait silencieusement une fiche.
5. Publier puis retirer → disparaît immédiatement des endpoints publics, les deux décisions restent auditées.
6. Vérifier qu'une source fictive n'apparaît jamais en mode `production`.

Exécuter dans le projet (Docker/PostGIS requis) :

```sh
python3 scripts/init_local.py
docker compose build
docker compose up -d db
docker compose run --rm api uv run --no-sync python backend/manage.py test catalog.tests.test_kickoff_vertical_slice --noinput -v 2
```

Puis la recette standard complète :

```sh
docker compose run --rm api uv run --no-sync python backend/manage.py test catalog.tests --noinput
uv run --frozen ruff check backend scripts
uv run --frozen ruff format --check backend scripts
```

**État de la recette :** tests ajoutés, **pas encore déclarés réussis** ; relever les résultats GitHub Actions de la PR et un contrôle navigateur réel si une démonstration complète de l'interface est prévue.

## 4. Travail en binôme et méthode de suivi

Un ticket comporte : **contexte**, **résultat visible**, **source / droits**, **périmètre exclu**, **critères d'acceptation**, **responsable**, **preuve** (test, capture, log), **blocages**. États : `À clarifier` → `Prêt` → `En cours` → `En revue` → `Terminé`.

- Tech lead : qualifier les sources et les risques, proposer une architecture limitée, découper, relire, documenter et débloquer.
- Autre bénévole : choisir ensemble une première tâche autonome, potentiellement parsing de source / tests / UI, selon son expérience et sa disponibilité.
- PO/PM et SOS : priorités produit, définition métier des métriques et validation éditoriale ; **aucune publication de données SOS sans leur accord**.
- Rituel : mise à jour asynchrone du ticket, courte synchronisation technique ; réunion projet du vendredi. Une ADR courte uniquement pour une décision qui affecte les autres bénévoles.

## 5. Questions fermées à poser vendredi

1. **A / B / C ?** Mettre à jour l'existant, remplacer la carte ou construire un outil complémentaire ?
2. Quel **parcours utilisateur** doit être présentable à la communauté le 7 novembre ?
3. Qui possède le Google Sheet et dispose d'une source **structurée plus récente** ?
4. Quelle est l'autorisation de **réutilisation, diffusion et précision géographique** des données ?
5. Où sont les vrais Figma, décisions, données, backlogs, hébergements et comptes ? Quel dépôt devient la source de vérité ?
6. Qui est le référent métier habilité à **valider les définitions et chiffres** ?
7. Quelle répartition avec le tech lead historique et le deuxième bénévole ? Quelles disponibilités réelles ?

**Décision du 30 octobre :** _à compléter avec les réponses, un responsable et une date._  
**Prochaine action :** _à compléter, uniquement après validation du périmètre._
