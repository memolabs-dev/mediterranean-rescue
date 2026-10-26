# Mediterranean Rescue — démonstration externe en 5 minutes

*Mis à jour le 26 octobre 2026. Prototype open source indépendant : aucune approbation officielle de SOS MEDITERRANEE ou de Data for Good n'est revendiquée.*

**Accès public** : https://rescue.memolabs.dev/  
**Code et traçabilité** : https://github.com/memolabs-dev/mediterranean-rescue  
**Carte de référence de l'association** : https://map.sosmediterranee.org/

## Une promesse simple

Le projet ne cherche **pas à remplacer la carte officielle existante**. Il expérimente la traçabilité d'événements issus des sources publiques, des contrôles avant publication, des décisions humaines consignées et des exports à destination du fonctionnement existant.

## Parcours public — sans identifiants

| Minute | Action à l'écran | Ce qu'il faut démontrer |
| --- | --- | --- |
| 00:00 | Accueil et avertissement d'indépendance | Expliquer ce qui relève de SOS MEDITERRANEE et du démonstrateur |
| 00:45 | Carte, flux, filtres | Rechercher une opération réelle dans les données déjà publiques |
| 02:00 | Ouvrir une fiche | Date, nature, source, précision géographique, décompte non cumulable |
| 03:15 | Ouvrir « À propos » | Provenance, limites, droits et processus humain de revue |
| 04:15 | Décrire le parcours équipe (sans connexion) | Contrôle bénévole, décisions enregistrées et retour au format de travail |
| 04:45 | Poser la question métier | « Quelle étape de votre flux actuel manque d'outillage ? » |

**Attention** : certains liens de provenance redirigent vers la carte générale et non une opération profonde. Le libellé de ces liens doit être précisé avant de présenter la provenance comme un deep-link systématique.

## Accès à l'espace équipe : politique de démonstration

L'espace privé est disponible à `/workspace`, mais **ne doit pas être exposé via un compte partagé**.

1. Pour la première prise de contact : démo publique et revue guidée par partage d'écran seulement.
2. Pour un essai externe : obtenir le nom et l'adresse de chaque relecteur autorisé, puis créer une invitation nominative à usage unique, à droits minimaux, dans **un environnement de démonstration isolé comportant uniquement des données fictives**.
3. Tester l'invitation avec une session privée neuve, depuis le même parcours que le destinataire. Vérifier le rôle, l'absence de droits de publication réels, l'expiration et la révocation.
4. Envoyer l'invitation séparément ; jamais de mot de passe, de jeton, de clé API ou de compte administrateur dans un PDF, une PR publique ou un courriel collectif.

**État** : le site public a été vérifié sur Chromium et WebKit après publication du 26 octobre. Le parcours invité externe de bout en bout n'a pas été certifié, donc aucun accès n'est promis à ce stade.

## Questions à poser avant toute proposition

- Quel est le problème le plus coûteux dans la vérification ou la reprise du tableur/cartographie actuel ?
- Quelles données peuvent légalement être reprises et publiées ?
- Qui est responsable d'une décision et de sa traçabilité ?
- Comment éviter les doublons et les totaux de personnes incorrects ?
- Le meilleur résultat serait-il une fonction, un module autonome, une intégration ou de la documentation ?

## Critères « prêt à envoyer »

- [ ] Site, accès et source de la démonstration vérifiés sur le dernier commit de production
- [ ] Aucun chiffre inventé, association clairement distincte du projet indépendant
- [ ] Parcours public reproductible en cinq minutes
- [ ] Parcours privé présenté **uniquement** si environnement isolé et compte nominatif testés
- [ ] Aucun email envoyé avant la validation explicite du dossier
