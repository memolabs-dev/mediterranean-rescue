# ADR 0011 : aperçu privé des vraies données sur l'écran principal

Statut : décidé le 24 octobre 2026 à la demande de Guillaume (« j'ai besoin de voir au fur et à mesure ce qui se passe sur l'écran principal ; pour l'instant je vois une map vide »).

## Problème
L'écran principal ne montre que des événements publiés. Rien n'est publié, et rien ne doit l'être sans décision humaine : la carte reste donc vide, alors que l'export réel est déjà enregistré en privé.

## Décision
- Une personne connectée avec le droit de revue voit sur l'écran principal un **aperçu privé** : les lignes du dernier export `Data_operations` et `Other_data` de chaque source, lues telles quelles, sur la carte et dans la liste, avec leur état de revue (à vérifier, bloquée, vérifiée).
- Un bandeau dit en clair que ces lignes ne sont ni vérifiées ni publiées. Un bouton bascule vers les seuls événements publiés.
- API en lecture seule, sous la session privée et le même droit que la revue : `GET /api/private/v1/preview/events/` (filtres de date, de catégorie et d'état, paginé), `GET /api/private/v1/preview/events/<ligne>/`, `GET /api/private/v1/preview/map-points/`. Seul le dernier export de chaque onglet est montré ; une position 0,0 n'est pas placée.
- Un visiteur ne voit aucun changement et n'appelle jamais ces routes.
- La fiche d'une ligne mène à sa vérification (`/workspace/review/...`).

## Ce que cela ne change pas
Aucune écriture, aucun événement créé, aucune publication. L'API publique reste inchangée. Les données réelles restent sur la machine locale et le tailnet privé.

## Itérations suivantes, dans l'ordre
1. Lire les 53 noms de ports : la fiche et la carte montrent alors le port réel de débarquement.
2. Écran principal : couleur des points par état, filtre par état, fiche plus riche (photos et témoignages cités par la source).
3. Revue en langage simple, depuis la fiche (« Vérifier cette ligne »).
4. Brouillons d'événements, puis publication contrôlée quand l'association l'aura décidé.
