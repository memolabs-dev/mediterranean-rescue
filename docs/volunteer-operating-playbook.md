# Mediterranean Rescue Atlas — guide d'exécution bénévole (proposition)

**Statut : brouillon de travail indépendant, non validé par Data for Good ni SOS MEDITERRANEE.**  
**Réunion de décision :** 30 octobre 2026. **Dépôt de travail :** `memolabs-dev/mediterranean-rescue`, distinct du dépôt `dataforgoodfr`.

## Ce que nous essayons de résoudre

SOS MEDITERRANEE dispose déjà d'une [carte CartONG](https://map.sosmediterranee.org/). Le prototype indépendant teste surtout **la chaîne de provenance et de validation** : récupérer une opération documentée, conserver son origine, signaler les incohérences, faire décider un humain, puis produire une représentation publique ou un export. Il ne présume ni du périmètre choisi par SOS, ni du droit de republier les données.

**Avant de développer davantage :** demander si l'équipe veut reprendre la carte actuelle, la remplacer, ou construire uniquement le workflow de revue et d'export. Les décisions sur les chiffres, la précision des positions et la publication reviennent à SOS et à la direction produit de Data for Good.

## 1. Premier parcours reproductible (données fictives)

- Exigences : Docker Compose, Node 24, pnpm 12.10.1 et Python 3.12+, voir [README](../README.md).
- Le parcours automatisé est [`frontend/e2e/kickoff-demo.e2e.ts`](../frontend/e2e/kickoff-demo.e2e.ts). Il teste avec une base isolée cinq événements **inventés**, dont deux publiés et un géolocalisé.
- La procédure locale et ses garde-fous sont décrits dans [`kickoff-technical-brief.md`](kickoff-technical-brief.md). **Ne jamais lancer la commande de seed sur la production ni sur une base contenant des données de SOS.**
- Une preuve de CI doit nommer le commit exact, l'exécution GitHub Actions et l'artefact de captures ; une CI verte ne vaut pas validation d'un déploiement extérieur ni accord de données.

## 2. Méthode de travail : un ticket = un résultat vérifiable

États : `À clarifier` → `Prêt` → `En cours` → `En revue` → `Terminé`. Un ticket bloqué reste visible avec un propriétaire de décision et une date de relance.

### Modèle à copier dans une issue

```markdown
## Pourquoi
Quel problème observé ? Lien vers le besoin, la carte existante et les sources.

## Résultat attendu
Une seule fonctionnalité ou preuve visible, sans hypothèse cachée.

## Données et droits
Fictives / publiques / privées ; provenance ; autorisation de copie et de publication.

## Périmètre exclu
Ce que le ticket ne changera pas (infrastructure SOS, données réelles, etc.).

## Critères d'acceptation
- [ ] Cas normal
- [ ] Cas d'erreur / donnée inconnue
- [ ] Permissions et retrait, si applicable
- [ ] Preuve : test / capture / URL de CI, commit exact
- [ ] Documentation de reprise

## Responsable, estimation, dépendance
Responsable : à attribuer. Estimation : h effectives (pas délai).
Relecteur : à attribuer. Décision externe requise : oui/non.
```

**P0** : sécurité, intégrité de données ou démonstration indispensable bloquée.  
**P1** : résultat du premier lot validé par le projet, à fournir rapidement.  
**P2** : qualité d'usage et ergonomie fondée sur un problème mesurable.  
**P3** : amélioration optionnelle, après P0/P1 et accord sur le périmètre.

## 3. Proposition de répartition à deux bénévoles (à valider)

| Travail | Tech lead | Deuxième bénévole |
| --- | --- | --- |
| Contrat de données, sources et droits | Responsable de la cohérence ; validation avec SOS | Cartographie du format et preuves d'anomalies |
| Import / export fictif | Relecture des cas métier et sécurité | Implémentation et tests reproductibles |
| Application / ergonomie | Critères d'acceptation et revue de PR | Une tâche UI ou E2E limitée |
| Décisions d'architecture | ADR courte et trade-offs | Avis technique, vérification |
| Communication externe | Préparer factuellement | Aucune publication sans accord du contact SOS/PO |

**Budget indicatif :** première itération 6–10 h par personne selon disponibilité (ce n'est pas une obligation). Pas de rôle ou d'assignation imposé sans échange préalable.

## 4. Suivi asynchrone hebdomadaire (copier-coller)

```markdown
### Rescue Atlas — semaine du AAAA-MM-JJ
- Livré : liens des PR fusionnées et preuves effectivement exécutées
- En cours : ticket, responsable, prochain critère d'acceptation
- Bloqué : fait manquant, décision attendue, personne à contacter
- Données : sources touchées, droits confirmés/non confirmés
- Risques : sécurité, publications, effets sur la carte existante
- Semaine suivante : maximum trois résultats observables
```

Une revue de PR vérifie la CI, les tests et une preuve E2E d'usage réel ; ne jamais déclarer prêt à cause de la seule compilation. En cas d'échec, le ticket reste en revue avec la cause et la marche à suivre.

## 5. Registre des décisions (ADR)

```markdown
# ADR-NNN — Une décision à la fois
Date / personnes consultées :
État : proposé | accepté | rejeté | remplacé
Contexte vérifié et sources :
Options envisagées :
Choix et responsable métier :
Conséquences (données, coûts, sécurité, réversibilité) :
Comment vérifier ce choix :
```

**ADR initiale à obtenir vendredi :** CartONG actuel vs refonte vs outil de complément. Tant que non décidé, rester sur tests synthétiques et composants indépendants. Voir [cadrage du kickoff](kickoff-technical-brief.md).

## 6. Candidats pour la première mission validable

- [#48](https://github.com/memolabs-dev/mediterranean-rescue/issues/48) : propriétaire des données, contrat observé, droits, format et décision de périmètre (à conduire avec SOS).
- [#49](https://github.com/memolabs-dev/mediterranean-rescue/issues/49) : export fictif compatible avec les colonnes CartONG, avec tests de round-trip, à lancer si le besoin est confirmé.
- [#45](https://github.com/memolabs-dev/mediterranean-rescue/issues/45) : preuve E2E du parcours bénévole authentifié sur données inventées.
- [#46](https://github.com/memolabs-dev/mediterranean-rescue/issues/46) : affichage effectif du point cartographique mobile.
- [#40](https://github.com/memolabs-dev/mediterranean-rescue/issues/40) : décision go/no-go de la démonstration publique et demandes de retour.

## 7. Transmission vers Data for Good

Ce dépôt reste un prototype indépendant. Si l'équipe choisit d'autres outils, **transmettre d'abord les contrats observés, les tests reproductibles, les scénarios métier et les conclusions** ; ne pas imposer les choix Django, PostGIS ou React ni envoyer de PR externe sans accord.

Demander explicitement le dépôt de référence, les personnes validant les données, le canal de suivi et la politique de confidentialité. Toute communication externe décrit le démonstrateur comme une proposition indépendante, jamais comme le site officiel ni une solution adoptée.
