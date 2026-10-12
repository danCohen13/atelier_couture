"""Règles de vie privée : dossiers inactifs, suppression ou anonymisation d'une cliente."""
import datetime

from django.db import transaction
from django.utils import timezone

from ..models import Client, Location, Paiement, Robe


def peut_etre_supprimee(cliente):
    """Une cliente sans robe ni location peut être effacée ; sinon la comptabilité l'exige."""
    return not cliente.robes.exists() and not cliente.locations.exists()


@transaction.atomic
def anonymiser_cliente(cliente):
    """Efface toutes les données personnelles mais garde les commandes, paiements et factures."""
    cliente.nom = 'Cliente'
    cliente.prenom = 'anonymisée'
    cliente.telephone = None
    cliente.email = None
    cliente.date_naissance = None
    cliente.tour_poitrine = cliente.tour_taille = cliente.tour_hanches = cliente.hauteur_buste = None
    cliente.notes_morphologie = None
    cliente.information_remise_le = None
    cliente.anonymisee_le = timezone.now()
    cliente.save()
    # Les notes libres des locations peuvent citer la cliente.
    cliente.locations.update(notes='', etat_avant='', etat_apres='')
    return cliente


def supprimer_ou_anonymiser(cliente):
    """Renvoie 'supprimee' ou 'anonymisee' selon ce que permet l'historique."""
    if peut_etre_supprimee(cliente):
        cliente.delete()
        return 'supprimee'
    anonymiser_cliente(cliente)
    return 'anonymisee'


def derniere_activite(cliente):
    """Date de la dernière trace d'activité (livraison, location, paiement, création du dossier)."""
    dates = []
    dates += list(cliente.robes.values_list('date_livraison', flat=True))
    for debut, fin, retour in cliente.locations.values_list('date_debut', 'date_fin_prevue', 'date_retour_effectif'):
        dates += [d for d in (debut, fin, retour) if d]
    dates += list(Paiement.objects.filter(robe__client=cliente).values_list('date', flat=True))
    dates += list(Paiement.objects.filter(location__client=cliente).values_list('date', flat=True))
    if cliente.cree_le:
        dates.append(timezone.localtime(cliente.cree_le).date())
    return max(dates) if dates else None


def clientes_inactives(annees, aujourdhui=None):
    """[(cliente, dernière_activité)] des dossiers sans activité depuis `annees` ans (hors anonymisés)."""
    aujourdhui = aujourdhui or timezone.localdate()
    try:
        limite = aujourdhui.replace(year=aujourdhui.year - annees)
    except ValueError:  # 29 février
        limite = aujourdhui.replace(year=aujourdhui.year - annees, day=28)
    resultat = []
    for cliente in Client.objects.filter(anonymisee_le__isnull=True).order_by('nom', 'prenom'):
        derniere = derniere_activite(cliente)
        if derniere is None or derniere < limite:
            resultat.append((cliente, derniere))
    return resultat
