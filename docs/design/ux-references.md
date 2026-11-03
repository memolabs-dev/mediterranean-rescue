# Références UX et décisions pour ce projet

Recherche du 24 octobre 2026. Objectif : une application compréhensible par des bénévoles qui ne travaillent pas quotidiennement dans l’outil. Les références ci-dessous éclairent nos choix ; leur efficacité dans notre contexte reste à tester. Aucun code, asset ou thème de ces produits n’est copié.

## Références retenues

| Référence primaire | Principe documenté | Application proposée |
| --- | --- | --- |
| [Nielsen Norman Group : reconnaissance et mémorisation](https://www.nngroup.com/articles/recognition-and-recall/) | Reconnaître parmi des options demande moins de rappel de mémoire | Afficher la ligne reçue, les valeurs interprétées et les candidats côte à côte ; ne pas demander un UUID à mémoriser |
| [GOV.UK : récapitulatif des erreurs](https://design-system.service.gov.uk/components/error-summary/) | Relier un résumé aux champs concernés et expliquer comment corriger | Cliquer une anomalie ouvre la ligne et le champ ; le même message reste visible près de la donnée |
| [GOV.UK : vérifier avant d’envoyer](https://design-system.service.gov.uk/patterns/check-answers/) | Montrer les réponses et permettre leur modification avant une soumission | Récapitulatif avant validation groupée ou publication, avec un bouton qui nomme son effet |
| [Carbon : tableaux de données](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines) | Barre d’outils, tri, sélection et actions groupées structurent les listes | Une liste de travail lisible, une sélection explicite et des actions limitées aux éléments éligibles |
| [OpenRefine : facettes](https://openrefine.org/docs/manual/facets) | Explorer une catégorie et son effectif réduit progressivement les lignes affichées | Compteurs cliquables « À examiner », « Bloquées », « Déjà liées », sans modifier les données |
| [Base UI : composants et accessibilité](https://base-ui.com/react/overview/quick-start) | Primitives d’interaction à composer et habiller | Utiliser les mécanismes de Field, Select, Combobox, Dialog, Checkbox et autres primitives installées, puis vérifier leur composition |

Nous retenons les principes de ces sources et l’identité SOS MEDITERRANEE. Nous n’adoptons ni leur bibliothèque de composants ni leur esthétique. Aucun de ces choix ne constitue une preuve d’utilisabilité de notre application.

## Décisions concrètes

### Deux espaces selon l’intention

Le public explore des événements publiés. L’équipe prépare et examine des données privées. Chacun trouve une navigation adaptée ; l’espace de travail ne devient pas un menu de commandes techniques. Le serveur reste responsable des autorisations.

### Une prochaine action compréhensible

Une page commence par son objet, son état et une action principale contextualisée. « Examiner les 3 anomalies » est préférable à un bouton « Continuer » sans effet expliqué. La première visite montre une tâche réalisable, pas six graphiques vides.

### Inspecter sans perdre sa place

Sur grand écran, une liste et un inspecteur latéral permettent de comparer les informations. L’ouverture garde filtres, page, défilement et sélection. Sur petit écran, le détail devient une page avec un retour qui restaure le contexte. Une décision complexe n’est pas comprimée dans une infobulle.

### Montrer progressivement, sans masquer l’essentiel

Date, type, effectif connu/inconnu et raison de revue apparaissent d’abord. La provenance complète et le contenu brut s’ouvrent à la demande. Les erreurs bloquantes, droits manquants et conséquences de publication restent visibles immédiatement.

### Sélectionner n’est pas approuver

Un filtre, une ligne sélectionnée ou un candidat suggéré ne modifie aucune identité. Les propositions portent un libellé expliquant leur origine. Une validation demande une action humaine et un motif. Les actions groupées ne s’appliquent qu’aux reports exacts éligibles et sont revérifiées côté serveur.

### Des interactions réactives, un état honnête

Filtrer, inspecter, comparer et revenir doivent être rapides. Un changement durable n’est confirmé qu’après réponse serveur. Un indicateur d’attente n’invente pas un pourcentage. Après une réponse réseau incertaine, relire l’état avant de réessayer une écriture.

### Pas de surprise en explorant la carte

Cliquer un résultat localise sa position connue ; cliquer un point ouvre son événement. Déplacer la carte ne change pas silencieusement les résultats : proposer « Rechercher dans cette zone ». Les données sans position restent dans la liste et sont comptées explicitement.

### Reprendre un travail interrompu

Les décisions enregistrées sont retrouvées côté serveur. Les saisies non soumises restent des brouillons en mémoire, sans promesse de sauvegarde automatique. Une fermeture avec saisie modifiée avertit ; un rechargement peut nécessiter une nouvelle saisie. Aucun contenu brut privé dans l’URL, localStorage ou l’analytique.

## Interactions utiles à concevoir

| Interaction | Bénéfice | Limite |
| --- | --- | --- |
| Facette avec compteur | Atteindre directement les lignes qui demandent une action | Le compteur décrit des lignes, pas des personnes |
| Comparaison reçu/interprété | Voir ce que le système a compris | L’original reste immuable |
| Inspecteur latéral | Examiner en conservant la liste | Passage à une page sur petit écran |
| Valider puis ouvrir la suivante | Réduire les manipulations répétées | Seulement après succès serveur, jamais automatique au focus |
| Sélection de plusieurs reports exacts | Éviter les validations identiques répétitives | Récapitulatif, motif, droits et revérification serveur |
| Filtres d’exploration partageables | Revenir à une période et partager un contexte public | Aucun identifiant privé ni cellule brute dans l’URL |
| État clair et retour explicite | Comprendre si une décision est enregistrée | Pas de simple toast éphémère comme seule preuve |

## Comment décider si c’est vraiment intuitif

Faire une première série de cinq séances courtes, avec des profils proches des bénévoles et lecteurs visés ; ce nombre organise une itération, pas une validation statistique. Demander d’agir sans expliquer d’abord les écrans. Observer les hésitations, retours arrière et demandes d’aide. Employer des fixtures synthétiques.

| Tâche | Objectif de conception à tester |
| --- | --- |
| Trouver où commencer un import | 4 participants sur5 identifient l’action en15 secondes sans aide |
| Trouver la première ligne bloquante d’un lot de20 lignes | 4 sur5 y arrivent en moins d’une minute et comprennent la cause |
| Comparer une proposition avec la ligne source | 4 sur5 expliquent ce qui sera lié avant de valider |
| Distinguer sélection, approbation et publication | Aucun participant ne croit qu’une sélection publie les données |
| Revenir du détail à la liste | Filtres, position et sélection conservés pour tous les essais |
| Effectuer le parcours critique au clavier | Tous les contrôles accessibles, focus visible et ordre compréhensible |
| Comprendre un effectif inconnu et un total d’événements | Aucune présentation qui conduit à les lire comme zéro ou personnes uniques |

Statut : protocole de test préparé, aucune séance réalisée. Une confusion sur publication, identité ou effectifs impose une correction avant passage au lot suivant. Les objectifs de temps se recalibrent après les premiers essais ; ils ne justifient pas de simplifier abusivement une décision métier.
