# Protection des données — document de référence de l'atelier

Cadre : loi israélienne sur la protection de la vie privée (1981, amendement 13 en vigueur depuis le 14 août 2025)
et règlement sur la sécurité des données (2017). Ce document décrit la base de données (règlement 2) ;
il se relit **une fois par an** et à chaque changement important (nouveau prestataire, nouvelle donnée).

> Ce n'est pas un avis juridique. Faire relire par un avocat israélien.

Dernière revue : ____ / ____ / ______   Par : ______________________

## 1. Description de la base

| Élément | Contenu |
|---|---|
| Responsable | Cohen Haute Couture (utilisatrice unique du site) |
| Personnes concernées | Clientes (confection sur mesure et location) |
| Données | Nom, prénom, téléphone, e-mail, date de naissance (facultative), mesures (poitrine, taille, hanches, hauteur de buste), notes de morphologie, commandes, locations, paiements, cautions |
| Données sensibles | Aucune donnée médicale ne doit être saisie (le champ « notes de morphologie » est réservé à la morphologie). Les montants facturés à une cliente sont des données financières : traitées avec le même soin |
| Finalités | Réaliser les commandes, gérer les locations, facturer, tenir la comptabilité, joindre la cliente |
| Pas de | publicité, revente, communication à des tiers |
| Nombre de personnes | Quelques centaines au maximum (très en dessous du seuil d'enregistrement de 10 000) |
| Utilisateurs autorisés | 1 (l'utilisatrice). Toute personne ajoutée doit être listée ici |

Régime de sécurité retenu : base gérée par une personne (au plus deux autres utilisateurs, moins de
10 000 personnes, pas de secret professionnel). Si le nombre d'utilisateurs ou la nature des données
change (données médicales, plus de deux utilisateurs), le niveau de sécurité augmente : refaire l'analyse.

## 2. Prestataires (sous-traitants) et transferts

| Prestataire | Rôle | Données | Lieu | À faire |
|---|---|---|---|---|
| Render | Hébergement du site | Tout (en transit et en mémoire) | Vérifier la région du service | Accepter et conserver l'accord de traitement (DPA) |
| Neon | Base PostgreSQL | Toutes les données | Vérifier la région du projet (idéalement Europe) | Idem |
| Cloudinary | Images (croquis, tissus, justificatifs, photos du stock) | Images, adresses publiques | Région par défaut : États-Unis ; une région Europe existe | Idem ; ne jamais y mettre de photo identifiable d'une cliente |
| Brevo | E-mails (code de réinitialisation du mot de passe) | Adresse e-mail de l'utilisatrice | Europe (société française) | Idem |
| Google (Gemini) | Analyse des dictées | Texte dicté (mesures, phrases comptables) | Hors Israël | Ne dicter aucun nom |

Les transferts vers l'Union européenne sont considérés comme adéquats par l'Autorité israélienne.
Pour les États-Unis, s'appuyer sur l'accord de traitement signé du prestataire (engagement écrit de
respecter les conditions israéliennes) et le conserver dans ce dossier.

## 3. Mesures de sécurité en place

- Connexion obligatoire, blocage après 5 échecs (django-axes), HTTPS forcé, cookies sécurisés, HSTS.
- Adresse de l'administration personnalisable (`ADMIN_URL`), mots de passe validés par Django.
- Code de réinitialisation à usage limité (tentatives plafonnées).
- Secrets uniquement dans des variables d'environnement (jamais dans le code).
- Base chiffrée au repos et en transit chez l'hébergeur, sauvegardes quotidiennes du prestataire.
- Dépendances à versions fixées et auditées (pip-audit).

À faire par l'utilisatrice : mot de passe long et unique, écran verrouillé, appareils à jour,
ne pas partager le compte, déconnexion sur un appareil partagé.

## 4. Durées de conservation

| Donnée | Durée |
|---|---|
| Commandes, paiements, factures | Durée légale de conservation des livres comptables (7 ans d'après les sources consultées — à confirmer avec le comptable) |
| Coordonnées, mesures, notes | Jusqu'à 3 ans sans activité (réglable : `CONSERVATION_ANNEES_INACTIVITE`), ou plus tôt sur demande |

Chaque année : ouvrir la page « Confidentialité » du site, passer en revue les dossiers inactifs et effacer
leurs données personnelles (les commandes et montants sont gardés sans lien avec l'identité).
Attention : le libellé libre d'une opération manuelle (ex. « Acompte robe Salomé ») peut contenir un nom ;
éviter les noms dans ces libellés.

## 5. Droits des clientes

Chaque cliente peut demander à consulter, corriger ou faire supprimer ses données. Réponse par écrit
(motivée en cas de refus).
- Consultation : bouton « Exporter PDF » du dossier cliente.
- Correction : « Ajuster la fiche ».
- Suppression : bouton « Effacer ses données » (suppression complète si aucune commande, sinon anonymisation).
- Information : fiche à imprimer depuis la page « Confidentialité », remise avant la prise de mesures ; la remise est enregistrée sur le dossier.

## 6. Incident de sécurité

1. Couper l'accès : changer le mot de passe, révoquer les clés (Render, Neon, Cloudinary, Brevo).
2. Noter l'incident dans le registre (administration > Incidents de sécurité) : date, ce qui s'est passé, données concernées, mesures.
3. Si des données ont été utilisées sans autorisation ou altérées de façon importante : **signaler immédiatement
   à l'Autorité israélienne de protection de la vie privée** et cocher « incident grave » dans le registre.
4. Informer les clientes concernées si l'Autorité le demande, ou si elles risquent un préjudice.

## 7. Revue annuelle (liste de contrôle)

- [ ] Liste des utilisateurs autorisés à jour
- [ ] Prestataires et lieux d'hébergement vérifiés, accords de traitement conservés
- [ ] Dossiers inactifs traités
- [ ] Registre des incidents relu
- [ ] Ce document relu et daté en haut
