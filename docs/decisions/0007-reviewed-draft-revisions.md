# ADR 0007 : révisions revues des brouillons

Statut : accepté par Guillaume le 24 octobre 2026 (« révisions revues des brouillons existants »). Dépend des ADR 0005 et 0006.

## Problème
Un export plus récent peut corriger une ligne déjà convertie en brouillon : effectif révisé, date ou position rectifiée. L'ADR 0006 la signale (`revision_needed`) sans rien écraser. Il faut une décision humaine, traçable, qui applique ou refuse la correction sans perdre ce qu'un éditeur a déjà modifié à la main.

## Décision
- **Proposition calculée** (`propose_revision`) : on compare, champ par champ (catégorie, date, titre, position, précision, effectifs, port), les valeurs enregistrées sur l'identité au moment du brouillon ou de la dernière révision appliquée (`drafted_values`) avec la traduction de la nouvelle ligne selon l'ADR 0006. On ne retraduit pas l'ancienne ligne : un alias approuvé entre-temps ne passe pas pour une modification manuelle. Seuls les champs qui changent forment la révision. Une ligne qui ne change aucun de ces champs donne une révision vide : l'appliquer en accuse réception et déplace la ligne d'origine.
- **Conflit** : si l'événement a été modifié à la main sur un champ que la révision veut changer, vers une valeur différente de la correction, la révision est refusée et les champs en conflit sont nommés. Un titre régénéré alors que la catégorie ou la date ont été modifiées à la main est aussi un conflit. Une modification manuelle sur un autre champ (résumé, par exemple) est conservée.
- **Application** (`apply_revision`) : seulement pour un brouillon ou un événement retiré, jamais pour un événement publié (retirer avant correction, règle existante). Le statut ne change pas : un événement retiré reste retiré, la republication passe par `set_publication`. La ligne d'origine de l'identité devient la nouvelle ligne.
- **Refus** (`reject_revision`) : possible seulement pour une proposition calculée (un conflit n'empêche pas de refuser), afin que la trace contienne les valeurs refusées. Le refus vaut pour ce changement précis (même ligne d'origine, même nouveau contenu) : la ligne est alors présentée `revision_rejected`. Un autre changement, y compris un retour à ce contenu après une autre révision appliquée, produit une nouvelle proposition.
- **Trace** (`EventRevision`) : événement, identité, ancienne et nouvelle lignes, changements (valeurs avant et après), décision (`applied` ou `rejected`), auteur, date, motif. Lecture seule dans l'administration.
- Mêmes garde-fous que les brouillons : export le plus récent seulement, effectifs cohérents, position 0,0 refusée, permission `catalog.change_event`, motif obligatoire. Aucune application groupée : chaque révision est une décision.

## Hors périmètre
Révisions d'un événement publié sans retrait, fusion ou scission d'identités, interface de revue (application React).

## Critères d'acceptation
- Changements exacts proposés ; application qui met à jour le brouillon, déplace la ligne d'origine, trace la décision, ne publie rien.
- Modification manuelle en conflit refusée avec les champs nommés ; modification manuelle hors révision conservée.
- Événement publié refusé ; événement retiré révisé et resté retiré.
- Refus tracé, même contenu ensuite `revision_rejected`, contenu nouveau de nouveau proposé.
- Effectifs incohérents, export ancien, ligne sans révision, permission ou motif manquants refusés ; régressions vertes.
