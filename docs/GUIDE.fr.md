# Mediterranée Rescue

Fondations d’une plateforme de cartographie historique des actions en Méditerranée : React, Base UI, MapLibre, Django, Django REST Framework et PostgreSQL/PostGIS.

Ce fork est une contribution en cours. Son périmètre et sa future adoption doivent être discutés avec Data for Good et SOS MEDITERRANEE. L’ancienne démonstration statique est conservée dans web/ comme historique ; elle n’est plus la base de l’application.

## Décisions et données

- [Document de départ et plan concret](PROJECT.md)
- [Architecture et limites de la première tranche](architecture.md)
- [Inventaire réel des sources et dictionnaire des trois onglets](data-catalog.md)
- [Décision REST et typage backend/frontend](decisions/0003-rest-openapi.md)
- [La donnée d’abord : diagnostic hors ligne des exports Sheets](decisions/0004-data-first.md)
- [Suivi et preuves](../.agent/project/state.json)

L’existant [CartONG/SOSMedDashboard](https://github.com/CartONG/SOSMedDashboard) a une carte et des données Sheets accessibles. Sa licence et les droits de republication des données ne sont pas établis. Aucun code ou dataset CartONG n’a été recopié dans cette plateforme. Le fond Natural Earth est du domaine public ; la provenance est conservée dans web/PROVENANCE.md.

## Démarrer en local

Première fois ? Le [guide d’accueil](BIENVENUE.md) explique tout pas à pas. En bref, avec Docker, make et Python 3 :

```sh
make dev
```

Interface : http://127.0.0.1:5173/, espace équipe : http://127.0.0.1:5173/workspace. Backend : http://127.0.0.1:8010/api/v1/events/. Un `.env` neuf démarre en mode `training`, avec cinq opérations fictives et le compte local `local-team` connecté automatiquement. Le mode production de données et le mode d’entraînement sont explicitement séparés par DATA_MODE. Aucun événement réel ne doit être étiqueté fictif pour contourner cette séparation.

Les mêmes étapes à la main, avec le frontend sur l’hôte (Node 24+, pnpm 12.10.1) :

```sh
python3 scripts/init_local.py
docker compose build
docker compose up -d db
docker compose run --rm api uv run --no-sync python backend/manage.py migrate --noinput
docker compose up -d api
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Le script crée .env avec permissions privées, sans afficher ses secrets ni remplacer un fichier existant. Ne pas le committer. La base n’a pas de port publié ; seuls l’API et le frontend sont accessibles sur l’interface locale. L’image PostGIS officielle amd64 est exécutée sous émulation sur Mac ARM. Les volumes persistent entre redémarrages ; ne pas les supprimer pour résoudre une erreur.

## Administration et publication

Créer un compte local sans mot de passe par défaut :

```sh
docker compose exec api uv run --no-sync python backend/manage.py createsuperuser
```

L’administration Django est à /admin/. Le serveur de développement local sert ses fichiers statiques ; le serveur WSGI de production requiert un proxy pour /static/. Voir infra/README.md. Un éditeur peut préparer des brouillons, mais la permission catalog.publish_event est requise pour publier/retirer. Les droits de la source et sa licence doivent avoir été approuvés. Une publication crée un audit ; les relations d’un événement publié sont gelées dans l’administration. Retirer puis corriger et revoir avant republication. L’API publique est exclusivement en lecture.

Les bénévoles n’ont pas besoin de l’administration : ils travaillent dans l’espace équipe (`/workspace`), qui va de la vérification à la publication ([ADR 0013](decisions/0013-publication-and-onboarding-in-the-team-space.md)). Les rôles sont des groupes créés par la migration `0008` : **Verify events**, **Prepare events**, **Publish events**, **Manual import**. Une personne du groupe **Coordinator**, avec l’accès à l’administration (`is_staff`), crée les comptes bénévoles, les active ou les désactive et leur donne ces rôles ; elle ne voit ni ne modifie les comptes d’équipe technique, ne peut pas nommer d’autres coordinateurs, et un compte n’est jamais supprimé (ses décisions restent attribuées). L’accord de publication d’une source se coche seulement par un superutilisateur, une fois l’accord écrit obtenu. L’administration suit la langue du navigateur (anglais ou français, `backend/locale`).

Sur une machine locale, la connexion peut être retirée : `LOCAL_AUTO_LOGIN=<identifiant>` connecte automatiquement chaque visiteur avec ce compte (actif, sans mot de passe utilisable suffit). Ce réglage n’est accepté qu’avec `DJANGO_ENV=development` ; en production le démarrage échoue. Il donne l’accès à toute personne qui atteint le serveur : à n’activer que sur un poste local ou un réseau privé.

Réglages de production liés au proxy (liste de contrôle Django) : `DJANGO_NUM_PROXIES` (nombre de proxys devant Django, 0 par défaut : `X-Forwarded-For` est ignoré pour la limite de connexions) et `DJANGO_BEHIND_TLS_PROXY=1` quand un proxy termine TLS et réécrit toujours `X-Forwarded-Proto`. La limite de connexions est comptée dans un cache partagé en base (`django_cache`, créé par la migration `0008`). `/admin/` n’a pas de limite propre : le restreindre au proxy (adresse ou VPN) avant toute mise en ligne.

## Journal de bord public de SOS

La carte publique de SOS s'arrête le 6 février 2024 ; le journal de bord de sosmediterranee.org continue. `docker compose run --rm api uv run --no-sync python backend/manage.py sync_logbook` en retrouve les opérations (une requête par seconde), les met en attente privée avec la phrase d'où chacune vient, et l'espace équipe permet de les vérifier puis de télécharger les lignes vérifiées au format du tableur. `--every 21600` relit toutes les six heures. Hors ligne : `python3 scripts/logbook_backfill.py` écrit les mêmes lignes et leur provenance dans `data/local/backfill`. Voir [ADR 0014](decisions/0014-public-logbook-as-a-source.md) et [le compte rendu](backfill-2024-2026.md).

## Importer un export autorisé

Créer une Source dans l’administration, puis placer le fichier local dans data/local/. Contrat canonique v1 : tableau JSON avec external_id stable, kind (rescue/transfer/medevac/incident/shipwreck/dead_missing), occurred_on (YYYY-MM-DD), title, source_url, people (entier ou null), longitude/latitude (nombres ou null ensemble), location_precision (unknown/approximate/reported), summary facultatif. Limite : 5 Mio, 10 000 lignes. Les inconnus restent null.

```sh
docker compose exec api uv run --no-sync python backend/manage.py import_events --source ma-source --file /app/data/local/export.json
docker compose exec api uv run --no-sync python backend/manage.py import_events --source ma-source --file /app/data/local/export.json --apply
```

La première commande valide et conserve un staging privé. --apply crée seulement des brouillons, atomiquement. Rejouer le même fichier ne duplique pas le lot ; rejouer un lot appliqué ne duplique pas les événements. Une identité existante exige une révision revue, pas un écrasement implicite. Le connecteur Sheets et son crosswalk font partie de la tranche suivante ; ils ne sont pas simulés ici.

## Diagnostiquer un export Sheets hors ligne

Avant tout import, chaque export CSV des onglets Data_operations, Other_data ou Data_ports peut être diagnostiqué sur l’hôte avec Python 3.12+, sans Docker, base ni réseau. Contrat observé : `contracts/sheets-v1.json` (non approuvé par l’association).

```sh
python3 scripts/diagnose_sheets.py --sheet Data_operations --input data/local/Data_operations.csv --output-dir data/local/diagnostic-2026-10-24/Data_operations
```

Le dossier de sortie doit être nouveau ; rien n’est jamais écrasé. Il reçoit, en 0700/0600 et protégés par un `.gitignore` local : `snapshot.csv` (copie exacte), `diagnostic.json` (cellules brutes, candidats, anomalies ligne/colonne/champ), `report.md` (compteurs et localisations, sans valeur source ; anglais par défaut, `--language fr` pour le français) et `MANIFEST.json`, écrit en dernier : sans lui, le paquet est incomplet. Statuts distincts : lecture du CSV (`complete`, `end_unverified` quand la dernière ligne n’a pas de fin de ligne, cas normal des exports Google, `partial`, `rejected`), normalisation (`blocked`, `needs_review`), identités `unresolved`, publication `disabled`. Codes de sortie : 0 paquet écrit sans erreur bloquante, 1 entrée refusée ou sortie impossible, 2 usage, 3 paquet écrit avec erreurs bloquantes. Aucun événement ni brouillon n’est créé.

`--synthetic` étiquette une fixture fictive. Exemples générés à partir des fixtures de `backend/catalog/tests/fixtures/sheets/` : [docs/examples/synthetic-diagnostic](examples/synthetic-diagnostic/). Tests sans Docker : `cd backend && python3 -m unittest catalog.tests.test_sheets` ; ils tournent aussi dans la suite Django ci-dessous.

## Correspondance des identités et référentiel des ports

Un export diagnostiqué peut être enregistré dans le staging privé, puis relié à des identités durables par une personne qui en a la permission (`catalog.review_identity`). Voir [ADR 0005](decisions/0005-identity-crosswalk-and-ports.md).

```sh
docker compose exec api uv run --no-sync python backend/manage.py stage_sheet --source ma-source --sheet Data_operations --file /app/data/local/Data_operations.csv --actor mon-compte
```

La commande affiche seulement des compteurs de propositions (`new`, `exact_carry`, `candidates`, `blocked`, `linked`, ou pour les ports `new_port`, `existing_port`). Les approbations passent par les services de `backend/catalog/crosswalk.py` ; l’administration montre ces enregistrements en lecture seule. Aucune proposition ne crée de lien, aucun événement n’est créé ni publié.

## Brouillons d’événements

Une identité approuvée devient un brouillon privé avec `catalog.drafts.create_drafts` (permission `catalog.add_event`, motif obligatoire) ; `plan_drafts` montre d’abord l’issue de chaque ligne sans rien écrire. Les lignes écartées (non liées, déjà en brouillon, à réviser, effectifs incohérents) sont toujours listées. Un brouillon existant n’est jamais écrasé, et la publication reste celle de l’administration (droits de la source, motif, audit). Voir [ADR 0006](decisions/0006-event-drafts-from-identities.md).

## Révisions revues des brouillons

Quand un export plus récent corrige une ligne déjà convertie (`revision_needed`), `catalog.revisions.propose_revision` montre les champs qui changeraient et ceux qu’un éditeur a modifiés à la main (conflit). `apply_revision` applique la correction si rien ne bloque ni n’entre en conflit ; `reject_revision` garde le refus tant que l’export porte ce contenu. Permission `catalog.change_event` et motif obligatoires ; un événement publié n’est jamais révisé (le retirer d’abord), un événement retiré le reste. Chaque décision est tracée (`EventRevision`). Voir [ADR 0007](decisions/0007-reviewed-draft-revisions.md).

## Contrat REST, types et vérification

```sh
docker compose run --rm api uv run --no-sync python backend/manage.py test catalog.tests --noinput
docker compose run --rm api uv run --no-sync python backend/manage.py makemigrations --check --dry-run
docker compose run --rm -T api uv run --no-sync python backend/manage.py spectacular --lang en --validate --fail-on-warn > contracts/openapi.yaml
cd frontend
pnpm codegen
pnpm test
pnpm build
cd ..
python3 scripts/check_contract_negative.py
```

Le contrat OpenAPI est généré et validé par le backend. openapi-typescript génère routes, paramètres et réponses consommés directement par openapi-fetch et TanStack Query. TypeScript est strict. Ne pas éditer manuellement contracts/openapi.yaml ni frontend/src/api/schema.d.ts. La CI refait cette chaîne et refuse les fichiers générés désynchronisés. Les erreurs HTTP ont un contrat explicite ; les champs publics sont une sélection autorisée, pas une exposition de tous les modèles.

Les tests backend tournent sur une vraie base PostGIS distincte, pas SQLite. Le compte DB local est non-superuser mais a CREATEDB pour ces tests ; ce privilège doit être retiré du rôle d’application en production. Les tests contiennent uniquement des fixtures indépendantes. Le test négatif prouve qu’une requête frontend sur un champ inexistant est refusée par TypeScript.

## Avant toute mise en service

L’application est une fondation de développement vérifiée, pas une plateforme déjà validée et exploitée par l’association. Restent notamment licence/contrat des données, migration Sheets, rapprochements, recette métier et accessibilité, contrôles d’identité/accès de production, sauvegarde/restauration testée, proxy TLS/static et supervision. Les étapes sont documentées dans l’architecture et ne sont pas déclarées réalisées. Aucun déploiement ni message vers l’association effectué.
