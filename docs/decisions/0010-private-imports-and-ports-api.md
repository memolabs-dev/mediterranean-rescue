# ADR 0010 : API privée d'import et de lecture des ports

Statut : décidé le 24 octobre 2026 dans la suite de l'API privée de revue (« continue à développer »). Étend l'ADR 0009 (sessions, CSRF, enveloppe d'erreurs) aux parcours d'import (nouvel import, diagnostic) et de ports (référentiel, examen d'un libellé) de `docs/design/user-flows.md`. Les services de l'ADR 0005 (`stage_snapshot`, `approve_port_alias`, `classify_port_label`) restent les seuls à écrire.

## Langage
Retour de Guillaume sur la file de revue et l'examen d'une ligne : le vocabulaire technique (identité, rattachement, snapshot) ne se comprend pas. Les écrans d'import et de ports disent d'abord en clair ce que fait chaque action (« Enregistrer cet export », « Ce nom désigne un port »), le terme technique ne vient qu'en aide. Les libellés de bouton de `user-flows.md` sont adaptés dans ce sens ; le comportement ne change pas.

## Droits
- Import : `catalog.add_sheetsnapshot` (déjà exigé par `stage_snapshot`). `me/` expose `stage_snapshot` à côté de `review_identity` pour que la navigation n'affiche que ce qui est permis.
- Liste et détail des imports : l'un des deux droits.
- Ports : `catalog.review_identity`.

## Import
- `GET imports/options/` : sources (id, clé, nom, synthétique), onglets, taille maximale (`max_bytes` du contrat).
- `POST imports/diagnose/` (multipart : `source`, `sheet`, `file`) : diagnostic sans rien écrire ni retenir. Réponse : état de lecture, compteurs, anomalies par code et par gravité, les 200 premières anomalies localisées (ligne, colonne, champ, code ; aucune valeur brute), `stageable` et son motif (`read_rejected`, `read_partial`, `file_errors`), et l'export déjà enregistré pour les mêmes octets et le même contrat. Le navigateur garde le fichier en mémoire ; un rechargement demande de le choisir à nouveau. Aucun identifiant n'est créé.
- `POST imports/` (même corps) : le serveur rediagnostique et appelle `stage_snapshot` ; `201` à la création, `200` avec `created: false` si cet export existe déjà, `400 invalid` (champ `file`) s'il n'est pas enregistrable. Il ne fait jamais confiance au diagnostic renvoyé par le navigateur.
- `GET imports/?limit=&offset=` : tous les onglets, les plus récents d'abord. `GET imports/<uuid>/` : métadonnées, qui l'a enregistré, lignes en erreur par code et, pour les onglets revus, les compteurs de la file de revue.
- Taille refusée avant lecture au-delà de `max_bytes` ; débit limité (portée `imports`, `IMPORT_RATE`, 30 par minute) sur les deux `POST`.

## Ports
Un « nom à lire » est un texte exact d'une source : un port de débarquement des opérations (dernier export `Data_operations`) ou un nom de la liste des ports (dernier export `Data_ports`). Un nom lu porte un `PortAlias`.
- Identifiant opaque `label_id` : 32 premiers caractères hexadécimaux du SHA-256 de `source_id`, saut de ligne, nom. Le nom brut n'apparaît jamais dans l'URL.
- `GET ports/labels/?status=to_read|read&limit=&offset=` : nom, source, occurrences dans les opérations, ligne de la liste des ports s'il y en a une (position ou erreurs), port suggéré (nom identique à la casse près, jamais appliqué seul), lecture enregistrée. Compteurs des deux facettes.
- `GET ports/labels/<label_id>/` : même contenu, plus les cellules reçues de la ligne de la liste des ports (pour une position ambiguë) et quelques lignes d'opérations où le nom apparaît (ligne, date).
- `POST ports/labels/<label_id>/decision/` : `{interpretation, ports?, new_port?, vessel?, reason}`.
  - `port` : exactement un port, existant (`ports: [id]`) ou nouveau (`new_port`, depuis la ligne de la liste des ports ou avec longitude et latitude explicites et motif) ;
  - `ports` : au moins deux ports existants (un nom comme « Port A / Port B ») ;
  - `vessel` : un navire existant ;
  - `not_a_port` : région, inconnu ou autre.
  Coordonnées WGS84 vérifiées et 0,0 refusé au serveur. Un nom déjà lu ou modifié entre-temps : `409 conflict`.
- `GET ports/?q=&limit=` : recherche de ports par nom. `GET vessels/` : navires connus. S'il n'y en a aucun, l'interface explique que la lecture « navire » attend un navire enregistré.

## Limites connues
- « Plusieurs ports » ne choisit que des ports déjà connus : il faut d'abord lire les noms de la liste des ports. Un port absent de cette liste se crée en lisant un nom comme « un port » avec une position saisie.
- Aucun navire ne peut être créé ici ; tant qu'aucun n'est enregistré (administration), la lecture « navire » est expliquée et refusée.
- Le nom brut reste visible dans l'écran privé (c'est l'objet de la lecture) mais jamais dans l'adresse.

## Hors périmètre
Brouillons et publication, création de navires, correction d'une lecture déjà enregistrée, rétention temporaire d'un fichier côté serveur.
