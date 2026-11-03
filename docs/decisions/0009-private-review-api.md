# ADR 0009 : API privée de revue

Statut : accepté par Guillaume le 24 octobre 2026 (« d'abord le contrat des API privées de revue : sessions, CSRF, permissions, erreurs »). Dépend des ADR 0003, 0005 et 0008, et des écrans « File de revue » et « Examiner une ligne » de `docs/design/user-flows.md`.

## Principes
- Préfixe `/api/private/v1/`, URL en anglais, distinct de l'API publique `/api/v1/` qui reste sans authentification et inchangée.
- **Session Django** : l'application a son propre écran de connexion, qui appelle `POST session/` (nom d'utilisateur et mot de passe) ; `DELETE session/` déconnecte. Aucun jeton dans le navigateur : seul le cookie de session `HttpOnly` porte l'état. La connexion fait tourner la session et le jeton CSRF (`login()` de Django), donc le client oublie son jeton et le relit.
- **CSRF** : toute écriture exige l'en-tête `X-CSRFToken`. Le cookie CSRF reste `HttpOnly` ; le frontend lit le jeton sur `GET /api/csrf/` et le renvoie. Origines de confiance : `CSRF_TRUSTED_ORIGINS`.
  - `POST session/` vérifie le CSRF explicitement : DRF ne l'impose qu'aux utilisateurs déjà authentifiés, et une connexion sans jeton ouvrirait la porte au *login CSRF*.
  - En production derrière un proxy TLS, l'origine publique doit figurer dans `CSRF_TRUSTED_ORIGINS` et `SECURE_PROXY_SSL_HEADER` doit être réglé, sinon Django compare une origine `https` à une requête qu'il croit `http` et refuse toute écriture.
  - En développement, le proxy Vite réécrit l'en-tête `Host` (`changeOrigin`) mais garde `Origin` : l'origine du serveur de développement (et celle d'un éventuel tunnel) doit donc être déclarée dans `CSRF_TRUSTED_ORIGINS` du backend local.
- **Connexion** : un seul message pour un nom inconnu, un mot de passe faux ou un compte inactif (`400 invalid_credentials`), pour ne pas révéler quels comptes existent. Débit limité par adresse (`ScopedRateThrottle`, portée `sign_in`, `SIGN_IN_RATE`, 10 par minute par défaut) ; au-delà, `429 throttled`.
- **Permissions** revérifiées côté serveur à chaque requête : utilisateur actif et `catalog.review_identity` pour toute la revue. Les services de l'ADR 0005 restent les seuls à écrire ; l'API ne réimplémente aucune règle.
- **Données privées** : réponses `Cache-Control: no-store` ; les URL ne portent que des identifiants opaques (UUID) et des critères sans valeur brute ; aucune donnée n'est conservée dans le stockage du navigateur.

## Erreurs
Même enveloppe que l'API publique, `{code, detail, errors?}`, avec des codes explicites pour l'API privée :

| Statut | Code | Sens pour l'interface |
| --- | --- | --- |
| 400 | `invalid` | Saisie à corriger, détail par champ dans `errors` |
| 401 | `not_authenticated` | Session absente ou expirée : se connecter puis relire l'état |
| 403 | `permission_denied` | Connecté mais sans le droit : le dire, sans masquer en « aucun résultat » |
| 403 | `csrf_failed` | Jeton absent ou périmé : le client relit le jeton et réessaie une fois |
| 404 | `not_found` | Identifiant inconnu ; `detail` reste générique (« Not found. ») et ne nomme aucun modèle |
| 405 | `method_not_allowed` | Méthode non prévue |
| 400 | `invalid_credentials` | Connexion refusée, message unique quel que soit le motif |
| 429 | `throttled` | Trop de tentatives de connexion : attendre |
| 409 | `conflict` | L'état a changé (autre relecteur, ligne déjà liée, identité déjà utilisée) ou la règle métier refuse : relire puis redécider ; `detail` explique sans valeur brute |

## Ressources
- `POST session/` : `{username, password}` ; renvoie la même charge que `me/`. `DELETE session/` : `204`.
- `GET me/` : nom d'utilisateur et droits utiles à l'interface (`review_identity`).
- `GET snapshots/?sheet=&limit=&offset=` : exports enregistrés (source, onglet, date, lignes, statut de lecture), les plus récents d'abord. Sans `sheet`, la liste se limite aux onglets revus (`Data_operations`, `Other_data`) ; la file refuse tout autre onglet (`400 invalid`).
- `GET review/rows/?snapshot=<uuid>&status=to_review|blocked|linked&limit=&offset=` : file paginée (25 par défaut, 100 au plus) d'un export, avec les compteurs des trois facettes exclusives. `to_review` regroupe les propositions `new`, `exact_carry` et `candidates`.
- `GET review/rows/<uuid>/` : la ligne reçue (en-têtes et cellules brutes, provenance), son interprétation, ses erreurs, la proposition et ses candidats résumés, ou la décision déjà enregistrée.
- `POST review/rows/<uuid>/decision/` : `{action: "create_identity" | "link", identity: <uuid>?, reason}` ; appelle `approve_link`. Un choix manuel est enregistré `reviewed_match`.
- `POST review/snapshots/<uuid>/exact-carries/` : `{rows: [<uuid>…], reason}` ; seules les lignes sélectionnées et encore éligibles, revérifiées au serveur, en une transaction ; sinon `409` sans rien écrire.
- `GET review/identities/?snapshot=<uuid>&q=&limit=` : identités de la même source et du même onglet pour la recherche de rattachement ; `q` filtre sur la date (préfixe AAAA-MM-JJ) ou le début de l'identifiant.

« Examiner plus tard » n'appelle aucune API : rien n'est créé.

## Hors périmètre
Import et diagnostic HTTP, ports (ADR 0010), brouillons et révisions, création de comptes et réinitialisation de mot de passe.
