"""Export de TOUTES les données d'un atelier (ZIP de fichiers CSV) : portabilité et sauvegarde personnelle.

Seules les lignes de l'atelier demandé sont lues (`.de(atelier)`).
"""
import csv
import io
import zipfile

from django.utils import timezone

from ..models import Client, DepenseRecurrente, Location, Paiement, Robe, RobeLocation, Tache, Transaction

# (nom du fichier, modèle)
TABLES = [
    ('clientes', Client), ('confections', Robe), ('etapes', Tache), ('paiements', Paiement),
    ('operations-finances', Transaction), ('depenses-recurrentes', DepenseRecurrente),
    ('robes-de-location', RobeLocation), ('locations', Location),
]


def _valeur(objet, champ):
    valeur = getattr(objet, champ.name)
    if valeur is None:
        return ''
    if champ.is_relation:
        return str(valeur)
    if hasattr(valeur, 'isoformat'):
        return valeur.isoformat()
    return str(valeur)


def _csv(modele, atelier):
    champs = [c for c in modele._meta.concrete_fields if c.name != 'atelier']
    sortie = io.StringIO()
    sortie.write('﻿')  # BOM : Excel lit correctement l'hébreu et les accents
    ecrivain = csv.writer(sortie, delimiter=';')
    ecrivain.writerow([str(c.verbose_name) for c in champs])
    for objet in modele.objects.de(atelier).select_related().order_by('pk'):
        ecrivain.writerow([_valeur(objet, c) for c in champs])
    return sortie.getvalue()


def zip_atelier(atelier):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, 'w', zipfile.ZIP_DEFLATED) as archive:
        for nom, modele in TABLES:
            archive.writestr(f'{nom}.csv', _csv(modele, atelier))
        archive.writestr('LISEZ-MOI.txt', f"{atelier.nom}\n{timezone.localdate():%Y-%m-%d}\n")
    return tampon.getvalue()
