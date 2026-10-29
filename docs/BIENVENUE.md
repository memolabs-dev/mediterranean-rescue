# Bienvenue sur Mediterranean Rescue

Ce guide t'emmène de zéro à ta première pull request. Compte une demi-heure pour l'installation
et la découverte. Aucune connaissance du projet n'est nécessaire, et tu peux contribuer sans
écrire de code : vérifier des données, traduire, tester sur téléphone, relire la doc.

## Le projet en deux minutes

SOS MEDITERRANEE secourt des personnes en mer depuis 2016. Sa carte publique
([map.sosmediterranee.org](https://map.sosmediterranee.org/)) lit un tableur qui n'est plus
rempli depuis février 2024, alors que l'équipage continue d'écrire chaque opération dans le
journal de bord du site.

Ce dépôt est un prototype indépendant qui :

- lit ces sources publiques et met chaque opération retrouvée **en attente de vérification** ;
- laisse une personne la comparer à la phrase d'où elle vient, puis la publier ou non ;
- affiche les opérations publiées sur une carte, avec leur source.

Rien n'est publié automatiquement. Ce n'est pas le site officiel de SOS MEDITERRANEE.

## Ce qu'il te faut

- **Docker** avec Compose ([Docker Desktop](https://docs.docker.com/get-started/get-docker/) sur Mac et Windows, Docker Engine sur Linux) ;
- **Git** et **make** (déjà présents sur Mac et Linux ; sous Windows, passe par [WSL 2](https://learn.microsoft.com/fr-fr/windows/wsl/install)) ;
- **Python 3**, seulement pour le petit script qui crée ton fichier `.env` (déjà présent sur Mac et Linux).

C'est tout. Pas de Node, de PostgreSQL ni de GDAL à installer : tout tourne dans Docker.

## Installer et lancer

```sh
git clone https://github.com/memolabs-dev/mediterranean-rescue.git
cd mediterranean-rescue
make dev
```

La première fois, comptez 5 à 10 minutes (Docker télécharge et construit les images). Ensuite,
`make dev` repart en quelques secondes.

Ouvre ensuite :

- <http://127.0.0.1:5173> : le site public, avec deux opérations **fictives** ;
- <http://127.0.0.1:5173/workspace> : l'espace équipe, où tu es déjà connecté sous le compte `local-team`.

Dans l'espace équipe, commence par **Practise** : un exercice de deux minutes sur une opération inventée.

### Ce que `make dev` fait pour toi

1. crée un fichier `.env` privé avec des secrets aléatoires, en **mode training** (données fictives seulement) ;
2. construit les images et démarre la base PostgreSQL/PostGIS ;
3. applique les migrations ;
4. charge cinq opérations fictives et le compte local `local-team` (sans mot de passe, sans accès à l'administration) ;
5. lance l'API Django et le serveur de développement du frontend, qui se recharge quand tu modifies un fichier.

### Les commandes utiles

| Commande | À quoi elle sert |
| --- | --- |
| `make dev` | Tout démarrer (ou redémarrer) |
| `make logs` | Suivre les journaux de l'API et du frontend |
| `make stop` | Tout arrêter ; la base est conservée |
| `make test` | Lancer les tests backend et frontend |
| `make check` | Tout ce que la CI vérifie, sauf les tests navigateur : à lancer avant d'ouvrir une PR |
| `make help` | La liste complète |

## Choisir une tâche

1. Regarde les [issues marquées `good first issue`](https://github.com/memolabs-dev/mediterranean-rescue/labels/good%20first%20issue). Si la liste est vide, demande sur le Mattermost du projet : on en prépare au fil des sprints.
2. Une tâche est prête quand elle dit pour qui on la fait, ce qui doit marcher à la fin, avec quelles données fictives, et qu'elle tient en une journée au plus.
3. Écris dans l'issue que tu la prends, pour qu'on ne soit pas deux dessus. Une question ? Pose-la dans l'issue ou sur le Mattermost du projet.

## Faire ta contribution

1. **Une branche par tâche**, depuis `main` : `git switch -c fix/filtre-date`.
2. **Des commits petits**, un objet chacun, en anglais et à l'impératif : `Add the date filter reset`.
3. **Un test d'abord** quand le comportement change.
4. **`make check`** doit passer.
5. **Ouvre la pull request** et remplis le modèle. Garde-la petite : une PR, un sujet.

Ensuite, la branche `main` est protégée :

- personne ne pousse directement sur `main`, même les mainteneurs ;
- une PR doit avoir une relecture approuvée et les quatre vérifications de la CI au vert
  (lint Python, tests et contrat, tests de bout en bout, image de production) ;
- les commentaires de relecture doivent être résolus ;
- la PR est fusionnée en un seul commit (squash), et sa branche est supprimée.

Chaque fusion dans `main` part en production sur <https://rescue.memolabs.dev> en quelques
minutes. C'est pour ça que la CI et la relecture ne se contournent pas.

## Les règles qui comptent

- **Aucune donnée réelle dans le dépôt**, ni dans un test, ni dans une capture, ni dans un outil d'IA. Les tests utilisent des données marquées fictives. Les vrais exports vont dans `data/local/`, que Git ignore.
- **Inconnu n'est pas zéro.** Une valeur absente reste vide. On n'invente ni position, ni nombre de personnes.
- **Rien de sensible dans les commits, les issues ou les PR.** L'association est exposée. Si tu as un doute, demande avant d'écrire.
- **Le code, les commits et les messages d'erreur sont en anglais** ; les textes de l'interface passent par `frontend/src/i18n/en.ts` et `fr.ts`.
- Les conventions détaillées sont dans [AGENTS.md](../AGENTS.md) et [CONTRIBUTING.md](../CONTRIBUTING.md).

## L'IA, si tu l'utilises

Elle n'est pas obligatoire. Si tu t'en sers (Claude Code, Copilot, Cursor...) :

- dis-le dans ta PR, case prévue dans le modèle ;
- l'outil lit [AGENTS.md](../AGENTS.md) ; ne le modifie pas pour ta tâche, propose plutôt une PR dédiée ;
- relis chaque ligne avant de pousser : tu restes l'auteur de ta PR ;
- garde des PR petites, une branche à la fois.

## Si quelque chose coince

| Symptôme | Solution |
| --- | --- |
| `port is already allocated` | Un autre programme utilise le port 5173 ou 8010. Arrête-le, ou `make stop` dans l'autre copie du dépôt. |
| `password authentication failed for user "rescue"` | La base a été créée avec un autre `.env` (par exemple une autre copie du dépôt). Lance plutôt `COMPOSE_PROJECT_NAME=rescue-bis make dev` pour avoir une base séparée. |
| La base démarre lentement sur un Mac récent | L'image PostGIS tourne en émulation sur les puces Apple. C'est normal, surtout la première fois. |
| Rien ne s'affiche sur le site | `make logs`, puis lis la dernière erreur. |
| « DATA_MODE is not training » | Ton `.env` date d'avant ce guide. Mets `DATA_MODE=training` et `LOCAL_AUTO_LOGIN=local-team` dedans, ajoute `api` à `DJANGO_ALLOWED_HOSTS`, puis relance `make dev`. |

Ne lance pas `docker compose down -v` pour dépanner : cette commande efface la base.

## Pour aller plus loin

- [Le guide détaillé](GUIDE.fr.md) : imports, rapprochements, brouillons, publication, administration
- [Les sources de données](data-catalog.md) et [le rattrapage du journal de bord](backfill-2024-2026.md)
- [L'architecture](architecture.md) et [les décisions](decisions/)
- [Le système de design](../DESIGN.md)
