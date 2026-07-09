#!/usr/bin/env bash
# exit on error
set -o errexit

# Installer les dépendances
pip install -r requirements.txt

# Collecter les fichiers statiques pour Tailwind / CSS
python manage.py collectstatic --no-input

# Appliquer les migrations sur la base PostgreSQL de Render
python manage.py migrate