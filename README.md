# Atelier Pro — gestion d'atelier de couture (SaaS multi-ateliers)

> « Atelier Pro » est un nom **provisoire** (variable `PRODUIT_NOM`). Le dépôt s'appelle encore `atelier_couture`.

Application web (Django) pour des **ateliers de couture sur mesure et de location de robes**. Chaque atelier a ses
propres comptes et ses propres données, totalement séparés des autres. Elle remplace le cahier et le tableur :
clientes et mesures, commandes en cours avec leurs étapes, stock et locations, planning, comptabilité, protection
des données, et un écran « Aujourd'hui » qui dit quoi traiter en premier.

- **Langues** : **hébreu par défaut** (affichage de droite à gauche), **français** au choix. **Fuseau** : `Asia/Jerusalem`.
  **Devise par défaut** : ₪ (shekel), avec € et $.
- **Inscription** : sur **invitation uniquement** (voir 1.8). Gratuit au lancement.
- **Hébergement** : Render (application) + Neon (base PostgreSQL) + Cloudinary (photos).
- **Documents du dépôt** : ce `README.md` (vue d'ensemble), [`CONTRIBUER.md`](CONTRIBUER.md) (guide pour modifier le code),
  [`docs/SAUVEGARDES.md`](docs/SAUVEGARDES.md), [`docs/PROTECTION_DES_DONNEES.md`](docs/PROTECTION_DES_DONNEES.md).
- **Public visé** : la personne qui administre le produit (parties 1 à 3 et 8) et toute personne qui maintient le
  code (parties 4 à 10 ; commencer par `CONTRIBUER.md`).

## Sommaire

1. [Ce que l'on peut faire avec l'application](#1-ce-que-lon-peut-faire-avec-lapplication)
2. [Services tiers utilisés](#2-services-tiers-utilisés)
3. [Variables d'environnement](#3-variables-denvironnement)
4. [Architecture du code (backend)](#4-architecture-du-code-backend)
5. [Interface (frontend), hébreu et droite-à-gauche](#5-interface-frontend-hébreu-et-droite-à-gauche)
6. [Sécurité et vie privée](#6-sécurité-et-vie-privée)
7. [Installer, tester, déployer](#7-installer-tester-déployer)
8. [Exploitation : administration, sauvegardes, performance, migration](#8-exploitation--administration-sauvegardes-performance-migration)
9. [Bugs potentiels, limites et risques connus](#9-bugs-potentiels-limites-et-risques-connus)
10. [Règles pour garder le code simple](#10-règles-pour-garder-le-code-simple)

---

## 1. Ce que l'on peut faire avec l'application

Tout l'accès à l'application (`/app/`) exige un compte rattaché à un atelier actif. Le menu donne accès à six espaces.
Une utilisatrice ne voit **jamais** les données d'un autre atelier.

### 1.1 Aujourd'hui (page d'accueil après connexion)

Un seul écran qui dit quoi traiter, du plus urgent au plus lointain :

- **À traiter maintenant** : livraisons en retard, retours de robes en retard, retraits manqués, paiements en
  retard, cautions à restituer.
- **Aujourd'hui** : livraisons, retraits et retours du jour.
- **Les 7 prochains jours**.

Chaque ligne indique la cliente, le retard ou l'échéance, le détail utile (étapes restantes, montant dû), un numéro
de téléphone cliquable et un lien vers le dossier. Les règles sont celles des pages Finances et Locations : un
chiffre ne peut pas différer d'une page à l'autre. Code : `services/aujourdhui.py`.

### 1.2 Atelier & modèles (confection sur mesure)

| Action | Où |
|---|---|
| Voir les commandes en cours, triées par urgence, prix ou nom, filtrées en cours / terminées / toutes | Tableau de bord (`/app/`) |
| Ajouter une cliente avec ses coordonnées et ses mesures (poitrine, taille, hanches, hauteur de buste) | « Ajouter une cliente » |
| **Dicter les mesures** au micro, en hébreu ou en français : l'IA les range dans les bons champs | Formulaire cliente, bouton micro |
| Ajouter une robe (une commande) : modèle, dates, coût du tissu, main-d'œuvre, prix, devise, heures de travail, croquis, photo de tissus | « Ajouter une robe » |
| Suivre l'avancement par **étapes** (toile d'essai, coupe, assemblage, finitions, ou étape libre) ; cocher une étape fait progresser la barre | Tiroir de la robe |
| Consulter la fiche d'une cliente et **exporter un PDF** | `/app/clientes/<id>/` |
| Rechercher une cliente par nom ou prénom | `/app/clientes/` |

> Vocabulaire : dans le code, **`Robe`** désigne une *commande sur mesure* ; **`RobeLocation`** une robe du *stock*.

### 1.3 Planning

Calendrier mensuel (FullCalendar) avec trois types d'évènements : **livraison** d'une robe, **retrait** d'une
location (la robe sort), **retour** prévu. Les livraisons dépassées et non terminées sont signalées en retard.

### 1.4 Locations & stock

- **Catalogue** des robes de location : référence (unique par atelier), taille, couleur, photo, prix et caution par
  défaut, coût de revient, statut physique (disponible, pressing, réparation, hors service).
- **Créer une location** : cliente, robe, dates, prix convenu, caution. Le formulaire **refuse un chevauchement**
  avec une autre réservation et applique un **délai de pressing** (tampon) entre deux locations.
- **Tableau de bord des locations** : en cours, réservées, terminées, retards.
- **Enregistrer un retour** : état au retour, restitution de la caution, **retenue partielle ou totale**.

### 1.5 Finances & bilans

Six onglets :

1. **Bilan** : argent entré, argent dépensé, bénéfice, reste à encaisser ; période (aujourd'hui, ce mois, cette
   année, tout) ; graphique d'évolution (semaines, mois, années) ; opérations du journal, **50 par page**.
2. **Impayés & prévisions** : paiements en retard à réclamer, cautions à suivre, revenus attendus.
3. **Rentabilité** : gain par robe et gain horaire réel, comparaison confection / location.
4. **Dépenses récurrentes** : loyer, abonnements… créés automatiquement chaque mois.
5. **Paramètres** : taux de change (€ et $ vers ₪) et objectif mensuel.
6. **Ajouter une opération** : recette ou dépense, catégorie, justificatif (lien) ; une phrase dictée peut être
   analysée par l'IA (« קניתי חוט משי ב-45 שקלים אתמול » ou « acheté du fil de soie 120 hier »).

Autres fonctions :

- **Paiements** par robe ou par location (acomptes, solde, mode de paiement) avec **reçu PDF**.
- **Devis, facture** en PDF pour une robe ou une location (documents de gestion interne, pas des factures fiscales).
- **Exports** : CSV du journal et PDF récapitulatif.

**Deux façons de compter** (sélecteur « Compter » sur la page Bilan) :

- **Le facturé** : une robe est comptée à sa date de livraison, une location à sa date de retrait, même si elle n'est
  pas encore payée. Le coût du tissu est une dépense à la date de commencement. Une caution retenue devient un
  revenu à la date de retour.
- **L'argent reçu** : seuls les paiements réellement encaissés comptent.

Les montants de devises différentes **ne s'additionnent jamais** sans taux de change : le total en ₪ n'utilise que
les taux saisis dans les paramètres.

### 1.6 Confidentialité et export des données

Page de suivi de la conformité à la loi israélienne sur la protection de la vie privée : fiche d'information
à remettre aux clientes (PDF), date de remise, **suppression ou anonymisation** d'une cliente, dossiers inactifs
(3 ans par défaut), registre des incidents de sécurité. Chaque atelier renseigne son nom et son contact de
confidentialité (formulaire « Mon atelier »).

**Exporter mes données** : la propriétaire télécharge toutes les données de son atelier (clientes, commandes,
paiements, locations, finances) en un ZIP de fichiers Excel (CSV). Détails : [`docs/PROTECTION_DES_DONNEES.md`](docs/PROTECTION_DES_DONNEES.md).

### 1.7 Connexion, langue et mot de passe oublié

- Après 5 échecs de connexion, le couple (adresse IP, identifiant) est bloqué 1 heure.
- Le mot de passe oublié passe par un **code à 6 chiffres envoyé par e-mail** (valable 10 minutes, 5 essais, un envoi
  par minute au plus), sans révéler si l'adresse existe.
- La langue se choisit dans l'en-tête (hébreu / français). Le choix est mémorisé dans un cookie et sur le compte.

### 1.8 Page d'accueil publique et inscription sur invitation

- La page d'accueil (`/`) présente le produit en hébreu ou en français et propose **« Demander une invitation »**
  (adresse e-mail + nom d'atelier). Un champ piège (`site_web`) écarte les robots.
- **Il n'existe pas d'inscription libre.** L'administrateur voit les demandes dans l'administration
  (*Demandes d'invitation*), les accepte par l'action « Envoyer une invitation », ou crée une invitation à la main
  (*Invitations*, ou `python manage.py inviter adresse "Nom d'atelier" --envoyer`).
- L'invitation est un **lien à usage unique, valable 7 jours** ; seul son hachage est conservé. La personne choisit
  son identifiant et son mot de passe : l'atelier et son compte de propriétaire sont créés ensemble.
- Une adresse e-mail reçoit un e-mail à chaque demande si `NOTIFIER_DEMANDES_A` est défini.

---

## 2. Services tiers utilisés

### Services dont dépend le fonctionnement

| Service | Rôle | Réglage | Si le service tombe |
|---|---|---|---|
| **Render** (render.com) | Héberge l'application (Gunicorn). Redéploie à chaque envoi sur `main`. | Région et plan dans *Settings* du service | Le site est inaccessible. Offre gratuite : mise en veille après 15 min d'inactivité, premier chargement lent. |
| **Neon** (neon.tech) | Base de données PostgreSQL. Contient toutes les données. | `DATABASE_URL` | Plus aucune donnée. Offre gratuite : mise en veille de la base après 5 min. |
| **Cloudinary** (cloudinary.com) | Stocke les photos : croquis, photos de tissus, photos du catalogue. | `CLOUDINARY_URL` ; nom du compte et préréglage d'envoi dans `base.html` | Les images ne s'affichent plus, le reste fonctionne. |
| **Brevo** (brevo.com) | Envoie les e-mails (invitations, codes de réinitialisation) par SMTP. | `BREVO_SMTP_KEY`, `EMAIL_HOST_USER`, `DEFAULT_FROM_EMAIL` | Plus d'invitation ni de mot de passe oublié par e-mail. |
| **Google Gemini** (API) | Analyse les dictées : mesures d'une cliente, opérations comptables. | `GEMINI_API_KEY`, `GEMINI_MODEL` | Les boutons « Analyser » affichent une erreur ; la saisie manuelle fonctionne toujours. |
| **Stockage S3 des sauvegardes** (Cloudflare R2, Backblaze B2…) | Reçoit chaque nuit la sauvegarde chiffrée de la base. À choisir **chez un autre fournisseur que Neon**. | `BACKUP_S3_*`, `BACKUP_ENCRYPTION_KEY` | Les sauvegardes ne partent plus ; `verifier_sauvegarde` le signale. |
| **GitHub** | Dépôt du code ; GitHub Actions lance les contrôles (`.github/workflows/ci.yml`). | — | Pas de déploiement automatique. |

### Ressources chargées par le navigateur (réseau de diffusion)

| Ressource | Source | Page |
|---|---|---|
| Chart.js 4 (graphiques) | cdn.jsdelivr.net | Finances |
| FullCalendar 6.1.15 + langues hébreu / français | cdn.jsdelivr.net | Planning |
| Flatpickr + langues hébreu / français (sélecteur de date) | cdn.jsdelivr.net | Formulaires |
| Polices (Cormorant Garamond, Inter, Heebo, Frank Ruhl Libre, IBM Plex Mono) | fonts.googleapis.com / fonts.gstatic.com | Toutes |
| Widget d'envoi de photos | upload-widget.cloudinary.com | Formulaires avec photo |

### Fonction du navigateur (pas un service du projet)

- **Dictée vocale** : reconnaissance vocale intégrée au navigateur (`SpeechRecognition`), réglée sur `he-IL` ou
  `fr-FR` selon la langue de l'interface. Sous Chrome et Edge, l'audio est traité par les serveurs du fournisseur
  du navigateur. Peu fiable sur Safari et Firefox.

### Bibliothèques Python (`requirements.txt`)

| Paquet | Usage |
|---|---|
| Django 5.2 | Framework web |
| django-axes | Blocage après échecs de connexion |
| whitenoise, gunicorn | Fichiers statiques, serveur d'application |
| dj-database-url, psycopg2-binary | Connexion PostgreSQL via `DATABASE_URL` |
| cloudinary, django-cloudinary-storage | Stockage des images |
| xhtml2pdf, reportlab, pillow | PDF et images |
| requests | Appels à l'API Gemini |
| python-dotenv | Lecture du fichier `.env` local |
| cryptography, boto3 | Chiffrement et dépôt des sauvegardes |

Développement (`requirements-dev.txt`) : `ruff`, `coverage`, `pip-audit`, `polib` (catalogues de traduction).

---

## 3. Variables d'environnement

Modèle complet dans `.env.example`. En local, copier ce fichier en `.env` (jamais commité).

| Variable | Obligatoire | Rôle |
|---|---|---|
| `DEBUG` | non | `True` en local uniquement. Absente ou `False` en production. |
| `SECRET_KEY` | **oui** en production | Clé secrète Django. |
| `DATABASE_URL` | **oui** en production | Chaîne PostgreSQL (Neon, adresse « pooled »). `sqlite:///db.sqlite3` accepté en local. |
| `ALLOWED_HOSTS` | non | Domaines personnalisés, séparés par des virgules (`.onrender.com` déjà accepté). |
| `SITE_URL` | recommandé | Adresse publique du site, utilisée dans les liens d'invitation. |
| `ADMIN_URL` | recommandé | Adresse de l'administration (défaut `admin/`) : en choisir une non devinable. |
| `NOTIFIER_DEMANDES_A` | recommandé | Adresse qui reçoit un e-mail à chaque demande d'invitation. |
| `PRODUIT_NOM` | non | Nom provisoire du produit (défaut « Atelier Pro »). |
| `SECURE_HSTS_SECONDS` | non | Durée HSTS (défaut 30 jours). |
| `BREVO_SMTP_KEY`, `EMAIL_HOST_USER`, `DEFAULT_FROM_EMAIL` | pour les e-mails | Sans clé en local, les e-mails s'affichent dans la console. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | pour l'IA | Clé et modèle. |
| `CLOUDINARY_URL` | pour les photos | `cloudinary://clé:secret@nom_du_compte`. |
| `BACKUP_ENCRYPTION_KEY` | pour les sauvegardes | Clé de chiffrement (`python manage.py sauvegarde --generer-cle`). **À conserver aussi hors de Render.** |
| `BACKUP_S3_BUCKET`, `BACKUP_S3_ENDPOINT`, `BACKUP_S3_ACCESS_KEY`, `BACKUP_S3_SECRET_KEY`, `BACKUP_S3_REGION`, `BACKUP_PREFIX` | pour les sauvegardes | Stockage S3 (voir `docs/SAUVEGARDES.md`). |
| `ATELIER_NOM`, `CONTACT_CONFIDENTIALITE` | non | Ne servent qu'à nommer le **premier atelier** lors de la migration des données existantes. |
| `CONSERVATION_ANNEES_INACTIVITE` | non | Durée avant proposition d'anonymisation (défaut 3). |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | non | PostgreSQL local quand `DATABASE_URL` est absente. |

---

## 4. Architecture du code (backend)

Une requête arrive, une **vue** la lit, un **service** fait le calcul, un **gabarit** affiche le résultat.
Le pas-à-pas pour modifier le code est dans [`CONTRIBUER.md`](CONTRIBUER.md).

```
config/                  réglages Django (settings.py) et routes racine (urls.py)
atelier/
  urls_publiques.py      routes SANS compte : accueil, connexion, invitation, langue, mot de passe oublié
  urls.py                routes de l'application (préfixe /app/), toutes protégées
  acces.py               @atelier_requis : exige un compte rattaché à un atelier actif
  langue.py              choix de la langue (cookie → compte → hébreu)
  invitations.py         liens et e-mails d'invitation
  contexte.py            variables communes aux gabarits
  models/                données, un fichier par domaine
    ateliers · clients · confection · location · finances · securite · constantes · mixins
  forms/                 formulaires, même découpage
  services/              logique métier SANS vue ni requête HTTP, testable seule
    aujourdhui.py        écran « Aujourd'hui »
    comptabilite/        calculs financiers
    confidentialite.py   effacement, anonymisation, dossiers inactifs
    export_atelier.py    export ZIP de CSV des données d'un atelier
    sauvegarde.py        sauvegarde chiffrée, stockage S3 ou local, rotation
    graphiques.py        séries du graphique
    gemini.py            transport vers l'API Gemini (seul endroit qui connaît clé, URL, modèle)
    extraction.py        consignes (prompts) hébreu et français
    pdf.py               génération des PDF
  management/commands/   creer_atelier · inviter · sauvegarde · verifier_sauvegarde · restaurer_sauvegarde · traductions
  views_*.py             une vue = lire la requête, appeler un service, rendre un gabarit
  templates/atelier/     gabarits HTML par domaine
  static/atelier/css/    style.css, planning.css, landing.css
  locale/                traductions hébreu (he) et français (fr), .po et .mo versionnés
  tests/                 un fichier de tests par domaine
docs/                    PROTECTION_DES_DONNEES.md, SAUVEGARDES.md
CONTRIBUER.md            guide pour modifier le code
build.sh                 build Render : dépendances, fichiers statiques, migrations
```

### 4.1 Isolation des ateliers (multi-tenancy)

Chaque modèle métier hérite de `ModeleAtelier` et porte une clé `atelier`. Un compte est rattaché à un atelier par une
`Adhesion` (un compte = un atelier ; rôle propriétaire ou employée). Règles :

- toute vue métier porte `@atelier_requis`, qui place l'atelier dans `request.atelier` (403 si le compte n'a pas
  d'atelier ou si l'atelier est suspendu) ;
- toute lecture passe par `Modele.objects.de(request.atelier)` ;
- un lien entre deux éléments d'ateliers différents est refusé à l'enregistrement ;
- `atelier/tests/test_isolation.py` vérifie qu'un atelier ne peut ni lire ni modifier les données d'un autre.

### 4.2 Modèles de données

```
Atelier ──< Adhesion >── User (compte)           Invitation, DemandeInvitation (avant l'inscription)
   │
   └── possède : Client ──< Robe (commande) ──< Tache
                    │            ├────< Paiement
                    │            └────< Transaction (liée, facultatif)
                    └────< Location >── RobeLocation (stock)
                               └────< Paiement
Transaction         écritures manuelles (recette ou dépense) ; peut venir d'une DepenseRecurrente
DepenseRecurrente   modèle de dépense mensuelle
ParametresFinance   taux de change, objectif mensuel (une ligne par atelier)
CodeReinitialisation, IncidentSecurite
```

- **Robe** : commande sur mesure ; propriétés calculées `progression`, `jours_restants`, `total_paye`, `reste_a_payer`.
- **RobeLocation / Location** : stock physique et contrat de location. `Location.clean()` interdit les
  chevauchements et applique le délai tampon.
- **Paiement** : rattaché à une robe **ou** à une location (jamais aux deux).
- `models/mixins.py` : `AvecDevise` et `AvecPaiements`, partagés.

### 4.3 Comptabilité (`services/comptabilite/`)

| Fichier | Rôle |
|---|---|
| `base.py` | Constantes, classe `LigneCompte` (une ligne du journal) |
| `ecritures.py` | Charge robes et locations en un seul passage, construit les lignes selon la base « facturé » ou « encaissé », génère les dépenses récurrentes |
| `conversion.py` | Totaux par devise, conversion en ₪ via les taux saisis |
| `analyses.py` | Comparaisons de périodes, objectif mensuel |
| `creances.py` | Impayés, cautions à suivre, prévisions, alertes |
| `rentabilite.py` | Gain par robe, gain horaire |
| `export.py` | Lignes pour l'export CSV |
| `tableau.py` | Assemble la page Bilan (dont la pagination du journal) |

### 4.4 Routes principales

| Zone | Exemples d'URL |
|---|---|
| Public | `/`, `/demande-invitation/`, `/invitation/<jeton>/`, `/connexion/`, `/langue/`, `/mot-de-passe-oublie/…` |
| Aujourd'hui | `/app/aujourdhui/` (arrivée après connexion) |
| Atelier | `/app/`, `/app/clientes/`, `/app/clientes/<id>/`, `/app/robe/ajouter/` |
| Planning | `/app/planning/`, `/app/api/planning/evenements/` |
| Location | `/app/location/catalogue/`, `/app/location/nouveau/`, `/app/location/<id>/retour/` |
| Finances | `/app/finances/`, `/app/finances/ajouter/`, `/app/finances/impayes/`, `/app/finances/rentabilite/` |
| IA | `/app/finances/analyser-ia/`, `/app/client/analyser-mesures/` |
| Confidentialité | `/app/confidentialite/`, `/app/confidentialite/export-donnees.zip` |
| Administration | `/<ADMIN_URL>` (réservée aux comptes « équipe ») |

Toute action qui modifie des données n'accepte que la méthode POST, avec jeton CSRF.

### 4.5 Intelligence artificielle

Deux fonctions, sur POST, réservées aux utilisateurs connectés :

1. **Mesures** : texte dicté (hébreu ou français) → JSON (`tour_poitrine`, `tour_taille`…).
2. **Opération comptable** : phrase → date, type, catégorie, désignation, montant. Le résultat **préremplit** le
   formulaire ; il n'enregistre rien tout seul.

Les consignes (`services/extraction.py`) expliquent à Gemini les nombres en toutes lettres, le vocabulaire de couture
et de comptabilité, le ₪ et les dates relatives en hébreu (la semaine commence le dimanche).

---

## 5. Interface (frontend), hébreu et droite-à-gauche

Pas de framework JavaScript : des **gabarits Django**, des fichiers CSS et du JavaScript écrit dans les pages.

| Élément | Fichier | Détail |
|---|---|---|
| Structure commune | `templates/atelier/base.html` | Menu, sélecteur de langue, messages, Flatpickr, widget Cloudinary |
| Style | `static/atelier/css/` | Thème « haute couture » : fond crème, serif, boutons noirs |
| Graphique | `finances/finances.html` + Chart.js | Données de `services/graphiques.py` |
| Calendrier | `planning/planning.html` + FullCalendar | Charge `/app/api/planning/evenements/` |
| Dictée vocale | `includes/_microphone_generic.html` | Reconnaissance du navigateur → IA → champs |
| Accueil public | `accueil.html`, `landing.css` | Présentation, demande d'invitation |
| PDF | `templates/atelier/pdf/` | xhtml2pdf, police Helvetica : **encore en français**, sans symbole ₪ (code `ILS`) |

**Hébreu et droite-à-gauche**

- La langue suit : cookie → langue du compte → **hébreu**. L'en-tête `Accept-Language` est ignoré (`atelier/langue.py`).
- Les textes du code sont **en français** ; l'hébreu est dans `atelier/locale/he/LC_MESSAGES/django.po`. Le catalogue
  `fr` doit rester identique à la source, sinon Django retombe sur l'hébreu. Les `.mo` sont versionnés.
- Ajouter un texte : `{% trans %}` dans un gabarit ou `gettext` en Python, puis `python manage.py traductions`,
  traduire les entrées vides du `.po` hébreu et relancer la commande. Un test échoue s'il manque une traduction ou
  si un `.mo` est périmé. Pièges : `CONTRIBUER.md`.
- Le CSS n'emploie que des propriétés **logiques** (`margin-inline-start`…) : un test interdit `left` et `right`.
  Numéros de téléphone : `dir="ltr"`.

---

## 6. Sécurité et vie privée

**En place**

- **Isolation entre ateliers** vérifiée par des tests ; accès refusé à un atelier suspendu.
- Connexion obligatoire sur toutes les pages métier ; blocage après 5 échecs (django-axes).
- Inscription sur invitation : lien à usage unique, hachage seul conservé, durée limitée.
- HTTPS forcé, cookies sécurisés, HSTS, adresse d'administration réglable.
- Mot de passe oublié sans énumération de comptes.
- Clé Gemini transmise dans un en-tête, jamais dans l'URL.
- Sauvegardes **toujours chiffrées** avant de quitter le serveur.
- Montants en `Decimal` ; aucune addition de devises différentes.
- Intégration continue : style, migrations, tests, audit des dépendances.

**Vie privée (loi israélienne, amendement 13)** : fiche d'information, preuve de remise, effacement ou
anonymisation, durée de conservation, registre des incidents, export des données. Voir `docs/PROTECTION_DES_DONNEES.md`.

**À savoir** : les mesures et notes envoyées à l'IA, ainsi que l'audio de la dictée selon le navigateur, partent chez
des prestataires hors d'Israël. La fiche d'information doit le mentionner.

---

## 7. Installer, tester, déployer

### Installation locale

```bash
python3.12 -m venv venv && source venv/bin/activate
python -m pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///db.sqlite3 DEBUG=True
python manage.py migrate
python manage.py creer_atelier "Mon atelier" mon_identifiant mon_mot_de_passe mon@email.com
python manage.py createsuperuser        # compte d'administration
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000/. Django 5.2 exige **PostgreSQL 14 ou plus** ; sinon utiliser SQLite comme ci-dessus.
Si `pip` manque dans le venv : `sudo apt install python3-venv python3-pip`, puis recréer le venv.

### Contrôles avant d'envoyer du code

```bash
ruff check .                              # erreurs et imports
python manage.py makemigrations --check   # aucune migration oubliée
python manage.py test atelier             # environ 395 tests, 2 à 3 minutes
coverage run manage.py test atelier && coverage report
pip-audit -r requirements.txt             # vulnérabilités des dépendances
```

Avec SQLite, les tests utilisent une base en mémoire. Ils tournent aussi sur GitHub à chaque envoi.

### Déploiement (Render)

`build.sh` installe les dépendances, rassemble les fichiers statiques et applique les migrations. Chaque envoi sur
`main` redéploie. Variables à définir : partie 3 (au minimum `SECRET_KEY`, `DATABASE_URL`).
**Avant de fusionner un changement de modèle dans `main`** : sauvegarde de la base (partie 8) et relecture de la
Pull Request. Les migrations 0013 et 0014 rattachent les données existantes à un premier atelier.

---

## 8. Exploitation : administration, sauvegardes, performance, migration

### Administration des ateliers (`/<ADMIN_URL>`)

Réservée aux comptes « équipe » (`is_staff`). Les comptes créés par invitation ne le sont **jamais**.

- **Demandes d'invitation** : voir les demandes, action « Envoyer une invitation aux demandes sélectionnées ».
- **Invitations** : en créer une à la main.
- **Ateliers** : statut (actif, essai, suspendu). **Suspendre** un atelier bloque ses accès sans effacer ses données.
- **Adhésions** et **Utilisateurs** : qui appartient à quel atelier ; décocher « actif » bloque un compte.
- **Incidents de sécurité** : registre à tenir à jour. **Axes** : tentatives et blocages de connexion.
- Vérifier régulièrement qu'**un seul** compte (le vôtre) est « équipe ».

### Sauvegardes

Deux filets : le retour dans le temps de Neon (erreurs récentes) et la **sauvegarde chiffrée quotidienne** hors de Neon.

```bash
python manage.py sauvegarde               # sauvegarde chiffrée vers le stockage S3 (ou --dossier ./dossier-local)
python manage.py verifier_sauvegarde      # alerte si la dernière a plus de 36 h, est illisible ou vide
python manage.py restaurer_sauvegarde --confirmer   # restaure dans une base VIDE uniquement
```

Mise en place, exercice de restauration et marche à suivre en cas de catastrophe : [`docs/SAUVEGARDES.md`](docs/SAUVEGARDES.md).
**Une sauvegarde jamais restaurée n'est pas une sauvegarde** : faire l'exercice une fois, puis chaque trimestre.
Les photos restent chez Cloudinary.

### Performance

- Page Finances : 92 requêtes et 1,1 Mo au départ, 10 requêtes et 64 Ko après optimisation (journal paginé,
  chargement partagé, GZip).
- **La région compte plus que le code** : Render et Neon dans la même région.
- Charge : Render → *Metrics*, Neon → *Monitoring*. Utiliser l'adresse « pooled » de Neon. Prévoir 3 processus Gunicorn ou plus.

### Changer la région de la base

La région d'un projet Neon ne se change pas : créer un nouveau projet, restaurer une sauvegarde chiffrée (ou
`dumpdata`/`loaddata`), comparer le nombre de lignes, remplacer `DATABASE_URL`, garder l'ancien projet une semaine.

---

## 9. Bugs potentiels, limites et risques connus

Rien ci-dessous n'empêche un lancement auprès de premiers ateliers ; ce sont les points à surveiller.

### Exploitation (à faire avant de vendre)

1. **Sauvegarde à mettre en route** : créer le bucket, la clé, les tâches planifiées, puis tester une restauration.
2. **Pas de surveillance ni de `/healthz/`** : une panne n'est vue que quand quelqu'un ouvre le site.
3. **Pas de double authentification**, y compris sur le compte d'administration qui voit tous les ateliers.
4. **Render et Neon gratuits : mise en veille.** À passer en offre payante avant de vrais clients.

### Fiabilité des données

5. **Suppression en cascade dans l'administration** : supprimer une cliente ou un atelier supprime aussi ses robes,
   locations et paiements. Préférer l'écran « Confidentialité » ; suspendre un atelier plutôt que le supprimer.
6. **Anonymisation partielle** : les URL de croquis et de tissus (Cloudinary) et les textes libres qui citeraient le nom restent.
7. **Taux de change non historisés** : modifier un taux change rétroactivement les totaux en ₪.
8. **Dépenses récurrentes générées à l'ouverture de la page Finances.**
9. **Pas d'historique des modifications.**
10. **Une seule propriétaire par atelier** : le rôle « employée » existe mais aucune interface pour en inviter.

### Hébreu et mobile

11. **Hébreu non relu** par une personne dont c'est la langue.
12. **PDF encore en français.**
13. **Adaptation au téléphone à améliorer** : zones tactiles, libellés de formulaires et étiquettes de tableaux
    à vérifier en hébreu, ligne de dictée qui déborde sur « Nouvelle cliente », calendrier à tester sur téléphone.

### Fonctionnement

14. **Dictée des mesures : « longueur de robe » ignorée** (pas de champ dans `Client`).
15. **Modèle Gemini retiré ou renommé** : changer `GEMINI_MODEL` sur Render, sans toucher au code.
16. **Aucune limite d'usage sur l'IA** : un appel bloque un processus jusqu'à 20 s ; risque de ralentissement et de facture.
17. **Dictée vocale selon le navigateur.**
18. **Filtres du tableau de bord et « Aujourd'hui » faits en Python** : sans problème jusqu'à quelques milliers de dossiers.
19. **Fuseau** : serveur en UTC, atelier en `Asia/Jerusalem` ; quelques tests utilisent `date.today()` et pourraient échouer près de minuit.
20. **PDF sans symbole ₪** (`ILS`).
21. **Documents de gestion, pas des factures fiscales** : à faire valider par un comptable avant tout usage officiel.

### Dépendances externes et sécurité

22. **Ressources CDN sans empreinte d'intégrité** ni version figée (`chart.js@4`, `flatpickr`) ; hors ligne, graphiques, calendrier et dates ne marchent pas.
23. **Envoi de photos Cloudinary non signé** : préréglage à restreindre (formats, taille, dossier) ou envoi signé.
24. **Photos accessibles par lien direct** et absentes des sauvegardes de la base.
25. **Pas de politique de sécurité des contenus (CSP).**
26. **Adresse IP prise dans `X-Forwarded-For`** (un seul proxy supposé) : correct sur Render.
27. **Données personnelles envoyées hors d'Israël** (Gemini, Cloudinary, Brevo, sauvegardes, reconnaissance vocale).
28. **L'isolation repose sur une convention** (`.de(request.atelier)`) gardée par des tests : voir `CONTRIBUER.md`.

---

## 10. Règles pour garder le code simple

- **Chaque donnée appartient à un atelier** : `Modele.objects.de(request.atelier)` partout, `@atelier_requis` sur toute vue métier.
- **Pas de calcul dans une vue** : il va dans `services/`, avec un test.
- **Un nouveau modèle** : dans le fichier de son domaine, hérite de `ModeleAtelier`, déclaré dans `models/__init__.py`, puis `makemigrations`.
- **Un nouveau formulaire** : dans `forms/` ; il n'expose jamais le champ `atelier`.
- **Les montants** restent en `Decimal` ; jamais d'addition de devises sans taux.
- **Toute action qui modifie des données** : POST, utilisateur connecté, jeton CSRF.
- **Tout texte affiché** passe par la traduction ; pas de `left` ni `right` en CSS.
- **Données de clientes** : relire `docs/PROTECTION_DES_DONNEES.md`. **Changement de modèle** : sauvegarde avant de déployer.
- **Avant d'envoyer** : `ruff`, `makemigrations --check`, tests (partie 7). Détails : `CONTRIBUER.md`.
