# Rescue Atlas — carnet de travail bénévole (proposition, 28 octobre 2026)

> **Indépendant / non validé par SOS MEDITERRANEE ou Data for Good.** Ce document et les tickets liés servent à cadrer la réunion du **vendredi 30 octobre 2026**. Il n'autorise pas la publication de données SOS, la réutilisation du tableur ni une migration de la carte officielle.

## Le résultat recherché — pas une deuxième carte par défaut

**Question à trancher avec l'équipe :** le nouvel Atlas doit-il (A) actualiser la carte CartONG existante, (B) la moderniser, ou (C) permettre aux bénévoles de vérifier et renvoyer des données vers la carte existante ?

Première preuve proposée, **sans données réelles** : une opération fictive arrive depuis un export au format observé, reste privée, reçoit une décision humaine motivée, puis est exportable dans le format historique sans doublon ni champ inventé. Une carte publique peut illustrer le résultat, mais n'est pas le livrable métier unique.

## Sources et gouvernance — état de connaissance

| Source | Ce qui est documenté | Responsable / droits / fraîcheur |
| --- | --- | --- |
| [Carte officielle SOS MEDITERRANEE](https://map.sosmediterranee.org/) | La carte existe et utilise historiquement des feuilles CartONG | Responsable opérationnel **à confirmer** ; aucune approbation écrite de republication enregistrée dans notre projet |
| [CartONG / SOSMedDashboard](https://github.com/CartONG/SOSMedDashboard) | Base historique, onglets `Data_operations`, `Other_data`, `Data_ports` ; audit des champs dans [data-catalog.md](data-catalog.md) | Mainteneur et cadence actuels **inconnus** ; dernière période exploitée dans notre audit : février 2024 |
| Journal de bord public SOS | Des opérations postérieures à février 2024 sont décrites en texte ; [audit préliminaire](backfill-2024-2026.md) | Toute extraction est une **candidate**, pas une ligne publiable ou un chiffre validé |
| [Prototype indépendant](https://github.com/memolabs-dev/mediterranean-rescue) | Django/PostGIS, React/MapLibre, staging, revue humaine, publication et tests synthétiques | Ne constitue ni une adoption par SOS ni la stack officielle Data for Good |

### Décisions à obtenir vendredi

| Décision | Décideur attendu | État |
| --- | --- | --- |
| A, B ou C : actualiser / moderniser / compléter CartONG | PO/PM + SOS | **En attente** |
| Qui maintient réellement les 3 feuilles et valide un événement | SOS / référent données | **En attente** |
| Droit de réutiliser, transformer et publier (avec précision géographique) | SOS / responsable autorisé | **Aucun accord écrit confirmé** |
| Premier utilisateur et résultat attendu au 7 novembre | PO/PM + SOS | **En attente** |
| Dépôt source de vérité, rôles, horaires, canal d'échange | Équipe Data for Good | **En attente** |

**Règle :** si l'un des champs est inconnu, ne pas le combler par une hypothèse. Mettre le ticket en `Bloqué — décision partenaire`.

## Sprint zéro — charge proposée de 8 à 14 h bénévoles réparties, hors attente SOS

| Ordre | Ticket | Livrable vérifiable | Charge indicative | Attribution proposée |
| --- | --- | --- | --- | --- |
| P0 | [#45](https://github.com/memolabs-dev/mediterranean-rescue/issues/45) | Parcours authentifié vérifié par navigateur en base fictive, rôles distincts, preuves | 3–5 h | Tech lead / test |
| P0 | [#46](https://github.com/memolabs-dev/mediterranean-rescue/issues/46) | Marqueur mobile réellement rendu et cliquable (test WebKit fait), validation sur vrai téléphone encore ouverte | 1–2 h | Front / QA |
| P1 | [#48](https://github.com/memolabs-dev/mediterranean-rescue/issues/48) | Décisions A/B/C, sources, responsables, droits et premier résultat | 2–4 h | Tech lead + PO/SOS |
| P1 | [#57](https://github.com/memolabs-dev/mediterranean-rescue/issues/57) | Exemple d'export CartONG depuis données fictives, mapping + non-régression | 3–5 h | Bénévole données |
| P1 | [#58](https://github.com/memolabs-dev/mediterranean-rescue/issues/58) | Méthode de rapprochement logbook / Sheets avec cas synthétiques | 3–5 h | Bénévole ingestion |

Ne pas attribuer nominativement d'autres bénévoles avant leur accord. Les charges sont **des estimations**, à recalibrer selon disponibilités.

## Définition commune d'un ticket

- **Contexte / source vérifiable** (lien et date) ; étiquette `confirmé`, `hypothèse` ou `bloqué`.
- **Résultat observable** : une page, un export, une décision ou un test ; ne pas confondre « code commité » et « démontré ».
- **Entrée et sortie** : exemple de donnée fictive, colonnes pertinentes, responsable de validation.
- **Critères d'acceptation** : permissions, idempotence, provenance, cas limites, comportements FR/EN et mobile si concernés.
- **Preuves** : URL de CI verte, test E2E exécuté, capture ou exemple de fichier (sans secrets ni vraie donnée privée).
- **Revue croisée** : un autre bénévole peut répéter la recette depuis un checkout propre.

États : `À clarifier` → `Prêt` → `En cours` → `En revue` → `Validé`, ou `Bloqué` avec décision requise et personne contactée.

## Deux boucles distinctes

**Boucle données** : source autorisée → empreinte / version → normalisation non destructive → revue contradictoire → décision avec motif → export / publication *si* autorisé → retrait traçable.

**Boucle GitHub** : issue de portée limitée → branche/PR → tests E2E sur base fictive → revue par pair → CI verte → merge → vérification réelle avant de dire « livré ».

## Un message de fin de réunion utile

« Notre démonstrateur indépendant est prêt à illustrer la vérification de sources. Nous ne proposons pas d'imposer sa stack. Pouvez-vous confirmer le problème le plus urgent de SOS, le propriétaire de la donnée et si notre premier livrable doit réactualiser le tableur CartONG, préparer un export contrôlé ou remplacer quelque chose ? »

Après réponse : consigner un **ADR-001** dans le dépôt choisi par l'équipe (pas automatiquement dans `dataforgoodfr`), dater la décision, désigner son responsable et n'ouvrir que les tickets validés.

## Ce que nous ne prétendons pas avoir fait

- Ni convention de réutilisation, ni validation scientifique/éditoriale des statistiques SOS.
- Ni transfert officiel de propriété du prototype ou changement d'infrastructure de l'association.
- Ni recrutement/affectation formelle de bénévoles.
- Ni diffusion publique d'un nouvel export de vraies opérations.

Suivi des blocages : [#40](https://github.com/memolabs-dev/mediterranean-rescue/issues/40), [#48](https://github.com/memolabs-dev/mediterranean-rescue/issues/48).
