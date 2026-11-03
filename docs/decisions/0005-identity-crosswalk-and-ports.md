# ADR 0005 : registre de correspondance des identités et référentiel des ports

Statut : accepté par Guillaume le 24 octobre 2026 (règle d'hémisphère validée, chantier lancé). Dépend de l'ADR 0004.

## Problème
Les onglets Sheets n'ont aucun identifiant d'événement stable : le numéro de ligne bouge, et date, position ou `nb_ops` ne suffisent pas à reconnaître une action d'un export à l'autre. Les ports sont des libellés libres (`Port_disembarkation`) et une liste `Data_ports` sans code ; trois de ses positions sont ambiguës faute d'hémisphère. Il faut une identité durable, attribuée et vérifiée par un humain, avant tout brouillon d'événement.

## Décision
Trois niveaux restent séparés (voir 03-modele-et-regles) : la ligne d'un snapshot, l'identité source approuvée, l'événement.

- **Snapshot persistant** (`SheetSnapshot`, `SheetRow`) : un export diagnostiqué est enregistré dans le staging privé avec son empreinte, la version du contrat, le statut de lecture, et pour chaque ligne les cellules brutes, le candidat normalisé, son empreinte canonique et ses codes d'erreur. Idempotent par (source, onglet, SHA-256, version du contrat) : les mêmes octets lus sous un nouveau contrat forment un nouveau snapshot. Refusé si la lecture est `rejected` ou `partial`, ou si une erreur touche le fichier entier. `end_unverified` est accepté et conservé.
- **Identité source** (`SourceIdentity`) : un UUID que nous attribuons, par source et onglet, créé seulement par une approbation humaine motivée. Il deviendra l'`external_id` du futur brouillon d'événement (`<onglet>:<uuid>`).
- **Lien ligne → identité** (`RowIdentityLink`) : seules les décisions approuvées sont stockées, avec auteur, motif et nature (`new`, `exact_carry`, `reviewed_match`). Une ligne a au plus une identité ; une identité apparaît au plus une fois par snapshot (contrainte SQL).
- **Propositions calculées, jamais stockées** : `exact_carry` quand l'empreinte du candidat n'a jamais été liée qu'à une seule identité, libre dans ce snapshot, que ce contenu n'y apparaît qu'une fois (lignes en erreur comprises) et qu'aucune autre ligne ne revendique cette identité ; `candidates` quand date et catégorie correspondent à au moins une identité ; `new` sinon ; `blocked` pour une ligne en erreur. Aucune proposition ne crée de lien : même le report exact demande un clic humain (approbation groupée possible). Seule l'approbation groupée enregistre `exact_carry` ; un choix manuel est toujours `reviewed_match`.
- **Référentiel des ports** : `Port` existe déjà ; il gagne sa provenance (`created_from`, ligne de `Data_ports`) et l'origine de sa position (`location_source` : ligne source ou relecteur). Une position 0,0 n'est jamais reprise automatiquement. `PortAlias` enregistre la lecture approuvée d'un libellé source exact, avec auteur et motif, unique par (source, libellé) : un ou plusieurs ports (`ports`), un navire (`vessel`, pour les transferts) ou « pas un port » (`not_a_port`, région ou inconnu). Constat sur l'export du 24 octobre 2026 : sur 49 libellés distincts de `Port_disembarkation` (307 lignes), 20 sont des noms exacts de `Data_ports` (220 lignes) ; les autres sont des navires de garde-côtes ou de marine, des navires d'ONG, des régions (Sicile, Calabre), des paires de ports (« Porto Empedocle & Civitavecchia »), des fautes (« Anconna », « Ravena ») ou une autre langue (« Valencia » pour « Valence »). Les propositions rapprochent seulement un nom identique à la casse près ; tout le reste est une décision humaine. Une ligne de `Data_ports` à position ambiguë ne crée un port qu'avec une position saisie explicitement par le relecteur.
- **Permission** : `catalog.review_identity` pour approuver identités, liens et alias ; `catalog.add_sheetsnapshot` pour enregistrer un snapshot.

## Hors périmètre
Création de brouillons d'événements depuis les identités (tranche suivante), interface de revue (future application React), rapprochement flou automatique, correspondance entre onglets (un transfert et le sauvetage d'origine), alias de ports pour d'autres sources.

## Critères d'acceptation
- Snapshot stocké avec provenance et empreintes, rejoué sans doublon, refusé si lecture rejetée ou partielle, sans création d'événement.
- Premier export, toutes les lignes saines proposées `new` ; approbation avec permission et motif, refus d'une ligne en erreur, d'un double lien, d'une identité vue deux fois dans un snapshot, d'une identité d'une autre source ou d'un autre onglet.
- Même contenu dans un nouvel export (lignes déplacées) : `exact_carry` vers la même identité, approbation groupée, aucune nouvelle identité. Ligne corrigée : `candidates`, puis `reviewed_match`. Empreinte dupliquée : jamais `exact_carry`.
- Ports proposés depuis `Data_ports`, port créé avec position et provenance, position explicite exigée pour une ligne ambiguë, lecture unique par libellé, libellés `Port_disembarkation` non résolus listés puis résolus ; libellé à plusieurs ports, navire ou « pas un port » enregistré sans être forcé vers un port ; seul un nom identique à la casse près est suggéré.
- API publique, publication et import canonique inchangés ; aucune donnée réelle dans le dépôt.
