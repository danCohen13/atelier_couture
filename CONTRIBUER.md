# Guide pour modifier le code

Ce guide est pour une développeuse ou un développeur qui découvre le projet. Comptez 15 minutes de lecture.
Les détails fonctionnels sont dans le `README.md`, la protection des données dans `docs/PROTECTION_DES_DONNEES.md`
et les sauvegardes dans `docs/SAUVEGARDES.md`.

## 1. Où est quoi

| Je veux… | Je regarde… |
|---|---|
| une page, ce qu'elle affiche | `atelier/urls.py` → la vue `atelier/views_*.py` → le gabarit `atelier/templates/atelier/` |
| un calcul (finances, retards, graphiques…) | `atelier/services/` (fonctions sans vue, faciles à tester) |
| un champ, une règle sur une donnée | `atelier/models/` (un fichier par domaine) puis `python manage.py makemigrations` |
| un formulaire | `atelier/forms/` |
| un texte à traduire | gabarit : `{% trans %}` ; Python : `gettext` (voir § 4) |
| le style | `atelier/static/atelier/css/style.css` (variables de couleurs en tête de fichier) |
| l'IA (dictée vocale) | `atelier/services/extraction.py` (consignes) et `gemini.py` (appel) |

Vocabulaire à connaître : **`Robe`** = une *commande sur mesure* (confection) ; **`RobeLocation`** = une robe du *stock*
que l'on loue ; **`Location`** = un contrat de location ; **`Atelier`** = un client du produit.

## 2. Les quatre règles à ne jamais enfreindre

1. **Chaque donnée appartient à un atelier.** Toute lecture passe par `Modele.objects.de(request.atelier)` et toute vue
   métier porte `@atelier_requis`. Un oubli ferait fuiter les données d'un atelier vers un autre.
   `atelier/tests/test_isolation.py` détecte la plupart des oublis : ne le contournez pas.
2. **Pas de calcul dans une vue** : il va dans `services/`, avec un test.
3. **Les montants sont des `Decimal`.** Les devises ne s'additionnent jamais sans taux de change.
4. **Toute action qui modifie des données** : méthode POST, utilisateur connecté, jeton CSRF.

## 3. Lancer les tests (à faire avant chaque envoi)

```
pip install -r requirements-dev.txt
DEBUG=1 DATABASE_URL=sqlite:///db.sqlite3 python manage.py test      # les tests utilisent une base en mémoire
ruff check .
python manage.py makemigrations --check
```
Les trois doivent passer. Tout nouveau comportement a son test (dossier `atelier/tests/`).

## 4. Ajouter ou changer un texte (hébreu / français)

- Les textes du code sont **en français** ; l'hébreu est dans `atelier/locale/he/LC_MESSAGES/django.po`.
- Gabarit : `{% load i18n %}` puis `{% trans "Texte" %}`. Avec une variable : `{% blocktrans with n=x %}…{{ n }}…{% endblocktrans %}`.
- Python : `gettext` dans une vue ou un service ; `gettext_lazy` dans un modèle ou un formulaire (évalué plus tard).
- Ensuite : `python manage.py traductions`, traduire les entrées vides du `.po` hébreu, relancer la commande.
  Les fichiers `.mo` compilés sont versionnés ; un test échoue s'il manque une traduction.
- Pièges : **aucun guillemet ASCII `"` dans une traduction hébraïque** (utiliser `״`) ; les textes injectés dans du JavaScript
  passent par `|escapejs` ; une apostrophe `'` dans un `{% trans '…' %}` casse l'extraction : utiliser `’` ou des guillemets doubles.

## 5. Affichage de droite à gauche (hébreu)

Le CSS n'utilise que des propriétés **logiques** (`margin-inline-start`, `padding-inline-end`, `text-align: start`…).
Les mots `left` et `right` sont interdits dans le CSS (un test le vérifie). Un numéro de téléphone ou un montant doit
rester de gauche à droite : `dir="ltr"` sur son élément.

## 6. Pièges de performance

- `Robe.progression` lit les étapes avec `self.taches.all()` : charger les robes avec `prefetch_related('taches')`, sinon une
  requête SQL part par robe. Même chose avec `'paiements'` pour `total_paye` et `reste_a_payer`.
- Les services chargent les dossiers d'un atelier en mémoire (`charger_dossiers`). C'est volontaire à l'échelle d'un atelier.

## 7. Envoyer un changement

Une branche par sujet, un message de commit qui dit **pourquoi**, les tests au vert, une relecture avant de fusionner
dans `main` (Render déploie automatiquement `main`). Changement qui touche des données de clientes : relire
`docs/PROTECTION_DES_DONNEES.md`. Changement de modèle : faire une sauvegarde (`docs/SAUVEGARDES.md`) avant de déployer.
