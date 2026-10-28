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

**Preuve vérifiée :** [CI GitHub Actions #69](https://github.com/memolabs-dev/mediterranean-rescue/actions/runs/40690823798), commit `8767857` : Python lint, Django/PostGIS + build, tests navigateur image de production et image finale réussis. Ce run vérifiait **7 nouveaux tests backend**. L'ajout de la commande locale ci-dessous et de ses tests nécessite **une nouvelle CI** avant fusion. Le run navigateur ne constitue **pas** une capture du nouveau scénario fictif.

### Démonstration visible sur une base locale isolée

La commande `seed_kickoff_demo` charge 5 **opérations entièrement fictives**, en publie 2 dans le mode `training`, et refuse son exécution en production, en mode non-debug ou sans confirmation. Elle ne crée aucun compte avec mot de passe utilisable. Éviter tout hébergement public ou les données réelles pour cet exercice.

Dans la racine du dépôt, avec Docker, Node 24 et pnpm :

```sh
python3 scripts/init_local.py
docker compose -p rescue-kickoff build db api
docker compose -p rescue-kickoff up -d db
docker compose -p rescue-kickoff run --rm -e DJANGO_ENV=development -e DATA_MODE=training api uv run --no-sync python backend/manage.py migrate --noinput
docker compose -p rescue-kickoff run --rm -e DJANGO_ENV=development -e DATA_MODE=training api uv run --no-sync python backend/manage.py seed_kickoff_demo --confirm-local-training
docker compose -p rescue-kickoff run --rm --service-ports -e DJANGO_ENV=development -e DATA_MODE=training api
```

Dans **un deuxième terminal** :

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Ouvrir `http://127.0.0.1:5173/` : le flux public doit contenir **2 entrées fictives**, dont **une seule position** sur la carte ; l'autre est sans localisation et sans effectif connu. Les 3 autres événements restent en brouillon. Pour vérifier les réponses API, consulter `/api/v1/events/` et `/api/v1/map-points/` via le serveur Vite.

Le projet Compose est volontairement nommé `rescue-kickoff` pour utiliser un volume PostGIS distinct du projet habituel. L'API d'entraînement n'est exposée que sur `127.0.0.1:8010`. Ne pas lancer un autre backend sur ce port. À la fin de l'exercice, arrêter le serveur et supprimer **uniquement** le volume de démonstration :

```sh
docker compose -p rescue-kickoff down -v
```

**Limite :** le contrôle navigateur manuel de cette procédure reste à exécuter ; la commande ne démontre pas à elle seule le parcours de validation dans l'interface d'équipe.

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
