# ADR 0003 : REST et contrat OpenAPI

Statut : accepté par Guillaume le 24 octobre 2026. Remplace ADR 0002 pour le code actif.

## Décision et périmètre
Django REST Framework expose une API JSON versionnée `/api/v1/`. drf-spectacular exporte OpenAPI ; openapi-typescript génère les types, openapi-fetch les consomme et TanStack Query gère le cycle des requêtes. Les services métier, modèles PostGIS, droits, staging et audit restent la référence. Aucun consommateur externe de GraphQL n’a été identifié dans ce fork non déployé : suppression de son endpoint et de ses dépendances, historique conservé dans Git.

## Contrat initial
GET `/api/v1/events/` : `start`, `end` ISO date, `kind` enum métier, `bbox` west,south,east,north ; `limit` 1..100 (25 par défaut), `offset` 0..100000. Réponse items, total_count, has_next, data_mode.
GET `/api/v1/events/{id}/` : détail publié, 404 pour inconnu/non public.
GET `/api/v1/map-points/` : mêmes filtres, maximum 2000 points, located_count, truncated.
GET `/api/v1/events/{id}/evidence/` : preuves paginées, mêmes garanties de visibilité.
GET `/api/v1/schema/` : contrat machine lisible.
Les listes et détails emploient des projections explicites ; aucun payload de staging, external_id, acteur ou audit public. Les filtres invalides, inconnus et répétés sont refusés (400). Les méthodes d’écriture sont refusées (405), la modification passe par l’admin avec sessions/CSRF.

## Exigences / acceptation de la tranche
- Liste, détail, points et preuves exposent seulement les événements publics selon les droits et DATA_MODE ; vérifier brouillons, retrait et révocation.
- Filtres cohérents, dates/bbox/enum/pagination validés ; vérifier 400, 404, 405, limite carte, budget SQL, absence des champs internes.
- OpenAPI validé sans avertissement et types générés déterministes ; mauvais endpoint/champ/paramètre refusé par TypeScript.
- Interface existante Base UI/MapLibre fonctionne avec le client REST ; chargement, vide, erreur/reprise, filtres et détail conservés.
- Document de départ décrit objectifs, inventaire, décisions, périmètre, lots dépendants, critères, risques, exploitation et onboarding ; README lance réellement la stack.

## Graphe et vérification
Étapes : spécifier (ce document), puis backend et contrat, client et interface, CI et régressions, enfin revue indépendante, document de départ et clôture.
Pas de migration de données nécessaire : changement de transport uniquement. Tests existants d’intégrité/publication/admin/import et réversibilité conservés. Tests HTTP remplacent tests GraphQL. Échantillons synthétiques seulement en tests, base locale réelle laissée vide. Production, connecteur Sheets et autorisations externes restent des lots futurs.

## Risques et limites
Une réponse typée n’est pas une validation de vérité ni une validation runtime du JSON côté navigateur. Sérialiseurs/test HTTP assurent le contrat serveur ; validation métier reste obligatoire à l’import. Les requêtes liste/carte sont séparées : un changement concurrent de publication peut produire une courte différence ; pas de promesse de snapshot atomique. Cache navigateur court et actualisation au retour de focus ; révocation effective à la prochaine requête. Aucun cache partagé durable avant politique de droits. Coordonnées longitude/latitude WGS84 ; bbox traversant l’antiméridien non supportée, 400. Aucun client public déjà déployé à migrer.

Sources : [DRF, documentation API](https://www.django-rest-framework.org/topics/documenting-your-api/), [drf-spectacular, CI](https://drf-spectacular.readthedocs.io/en/latest/client_generation.html), [client OpenAPI](https://openapi-ts.dev/openapi-fetch/).
