# Cohen Haute Couture — gestion d'atelier

Application Django à usage d'une seule personne : clientes, robes sur mesure, locations et stock,
planning, finances et protection des données. Hébergée sur Render, base PostgreSQL chez Neon.

## Installer et lancer en local

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///db.sqlite3 DEBUG=True
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Les variables d'environnement sont listées dans `.env.example`. En production, `SECRET_KEY` et
`DATABASE_URL` sont obligatoires.

## Contrôles avant d'envoyer du code

```bash
ruff check .                              # erreurs et imports
python manage.py makemigrations --check   # aucune migration oubliée
python manage.py test atelier             # tests
coverage run manage.py test atelier && coverage report   # couverture
pip-audit -r requirements.txt             # vulnérabilités des dépendances
```

Ces contrôles tournent aussi automatiquement sur GitHub (`.github/workflows/ci.yml`).

## Où trouver quoi

```
config/                  réglages Django et routes principales
atelier/
  models/                données, un fichier par domaine
    clients · confection · location · finances · securite · constantes
  forms/                 formulaires, même découpage (+ commun : champs de date jj/mm/aaaa)
  services/              logique métier SANS vue ni requête HTTP, testable seule
    comptabilite/        calculs financiers (écritures, bilan, créances, rentabilité, tableau de bord)
    confidentialite.py   effacement / anonymisation, dossiers inactifs
    graphiques.py        séries du graphique
    gemini.py · extraction.py   IA (transport / consignes)
    pdf.py               génération de PDF
  views_*.py             une vue = lire la requête, appeler un service, rendre un gabarit
    atelier · location · planning · auth · confidentialite
    finances (bilan, saisie) · paiements · documents (exports, PDF) · reglages_finance
  templates/atelier/     gabarits HTML par domaine
  static/atelier/css/    style.css
  tests/                 un fichier de tests par domaine
docs/PROTECTION_DES_DONNEES.md   description de la base, prestataires, conservation, incidents
```

## Règles pour garder le code simple

- **Pas de calcul dans une vue** : il va dans `services/`, avec un test.
- **Un nouveau modèle** va dans le fichier de son domaine et se déclare dans `models/__init__.py` ;
  puis `python manage.py makemigrations`.
- **Un nouveau formulaire** : même logique dans `forms/`.
- **Les montants** restent en `Decimal` ; les devises ne s'additionnent jamais sans taux de change.
- **Changement qui touche des données de clientes** : relire `docs/PROTECTION_DES_DONNEES.md`.

## Déploiement (Render)

`build.sh` installe les dépendances, rassemble les fichiers statiques et applique les migrations.
Chaque envoi sur `main` redéploie. Avant d'envoyer, vérifier que les contrôles ci-dessus sont verts.
Réglages à définir sur Render : voir `.env.example` (dont `CONTACT_CONFIDENTIALITE`).
