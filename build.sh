#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Le drapeau --clear nettoie les résidus des builds précédents
python manage.py collectstatic --no-input --clear
python manage.py migrate