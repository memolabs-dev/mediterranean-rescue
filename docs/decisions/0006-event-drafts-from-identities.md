# ADR 0006 : brouillons d'événements depuis les identités approuvées

Statut : accepté par Guillaume le 24 octobre 2026 (« brouillons, sans publication automatique »). Dépend des ADR 0004 et 0005.

## Décision
Une identité source approuvée (ADR 0005) peut devenir un **brouillon** d'événement. Le brouillon reprend la ligne du snapshot traité qui est liée à l'identité, avec une traduction explicite et prudente des champs ; il reste privé tant que la publication existante (`set_publication` : permission, droits et licence de la source, motif, audit) n'a pas été faite à la main. Rien n'est jamais publié par cette tranche.

## Règles de traduction
- `external_id` = `<onglet>:<uuid de l'identité>` ; `source` = source de l'identité ; `source_url` = URL de la source (aucune URL par ligne n'existe dans les onglets).
- `kind` et `occurred_on` repris du candidat ; titre généré en anglais (`Rescue on 2024-02-03`), langue par défaut du produit.
- Effectifs, Data_operations seulement : `people` = `nb_survivor`, `women` = `female`, `minors` = `under_18` ; inconnu reste `null`. Other_data : `people` reste `null`, `death_nb_people` n'alimente **jamais** un effectif de personnes secourues.
- Une sous-population supérieure à son total viole les contraintes existantes : la ligne n'est pas convertie, elle est signalée (`inconsistent_counts`), rien n'est tronqué ni corrigé.
- Position : celle du candidat, précision `reported`, y compris quand l'hémisphère a été déduit par la règle de région validée par Guillaume (le format d'origine reste sur la ligne source, `drafted_from`) ; pas de position, `unknown`. Une position 0,0 n'est jamais reprise : la ligne est écartée (`position_to_review`).
- Port : seulement si le libellé de débarquement a une lecture approuvée vers **un seul** port ; plusieurs ports, navire, « pas un port » ou libellé non lu laissent `port` vide.
- Témoignages, images, vidéos : non repris (droits non établis) ; ils restent dans le staging.

## Plan, puis création
`plan_drafts(snapshot)` calcule pour chaque ligne une issue sans rien écrire : `ready`, `not_linked`, `already_drafted`, `revision_needed` (l'identité a déjà un brouillon et la ligne a changé), `inconsistent_counts`, `position_to_review` (0,0), `row_already_drafted` (ligne déjà à l'origine d'un autre brouillon), `invalid_draft` (avec les noms des champs en cause), `stale_snapshot` (un export plus récent existe pour cet onglet), `not_an_event_sheet` (Data_ports). `create_drafts(snapshot, actor, reason)` crée, dans une seule transaction, les brouillons des lignes `ready` et renvoie aussi les lignes écartées avec leur raison : rien n'est écarté en silence. Permission `catalog.add_event` et motif obligatoires. L'identité garde la trace : brouillon, ligne d'origine, auteur, date et motif.

Un brouillon existant n'est jamais écrasé : une ligne corrigée produit `revision_needed`, qui relève d'une future tranche de révisions revues.

## Hors périmètre
Révisions d'un brouillon existant, preuves documentaires, rattachement voyage et navire, interface de revue (application React).

## Critères d'acceptation
- Brouillons créés avec les bons champs, statut `draft`, invisibles dans l'API publique, aucun audit de publication.
- Deuxième passage sans doublon (`already_drafted`) ; ligne corrigée `revision_needed` sans écrasement.
- Effectifs incohérents écartés et listés ; décès jamais copiés vers `people` ; inconnus restés `null`.
- Port rempli seulement pour une lecture vers un seul port ; Data_ports refusé ; permission et motif exigés.
- Publication toujours soumise à `set_publication` (droits de la source) ; régressions socle, diagnostic et correspondances vertes.
