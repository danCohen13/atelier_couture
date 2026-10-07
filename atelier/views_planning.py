"""
Planning mensuel de l'atelier.

- `planning`                 : page HTML qui héberge le calendrier (FullCalendar).
- `api_planning_evenements`  : endpoint JSON appelé par FullCalendar à chaque
                               changement de période affichée (?start=...&end=...).

Trois types d'évènements, tous à la journée :
    livraison : Robe.date_livraison           (confection sur mesure)
    retrait   : Location.date_debut           (la robe sort de l'atelier)
    retour    : Location.date_fin_prevue      (la robe doit revenir)
"""
import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Robe, Location

# Garde-fou : FullCalendar demande au plus ~6 semaines en vue mensuelle.
DUREE_MAX_JOURS = 120


def _jour(valeur):
    """Extrait la date d'un paramètre FullCalendar ('2026-10-01' ou '2026-10-01T00:00:00+02:00')."""
    if not valeur:
        raise ValueError("paramètre manquant")
    return datetime.date.fromisoformat(valeur[:10])


def _fmt(d):
    return d.strftime('%d/%m/%Y') if d else '—'


def _nom_cliente(client):
    return f"{client.nom.upper()} {client.prenom}"


@login_required
def planning(request):
    """Page du calendrier. Les évènements sont chargés en AJAX."""
    return render(request, 'atelier/planning/planning.html', {
        'url_evenements': reverse('api_planning_evenements'),
    })


def _evenement_livraison(robe, aujourdhui):
    progression = robe.progression  # tâches préchargées : aucune requête en plus
    echue = robe.date_livraison < aujourdhui
    classes = ['ev', 'ev--livraison']
    if echue and progression == 100:
        classes.append('ev--fait')
    elif echue:
        classes.append('ev--retard')  # date dépassée alors que la confection n'est pas terminée

    return {
        'id': f'livraison-{robe.pk}',
        'title': robe.nom_modele,
        'start': robe.date_livraison.isoformat(),
        'allDay': True,
        'classNames': classes,
        'extendedProps': {
            'kind': 'livraison',
            'kind_label': 'Livraison',
            'client': _nom_cliente(robe.client),
            'telephone': robe.client.telephone or '',
            'lignes': [
                ['Cliente', _nom_cliente(robe.client)],
                ['Livraison', _fmt(robe.date_livraison)],
                ['Avancement', f'{progression} %'],
                ['Prix total', f'{robe.prix_total} {robe.symbole_devise}'],
            ],
            'actions': [
                {'label': 'Modifier la confection', 'url': reverse('modifier_robe', args=[robe.pk])},
                {'label': 'Dossier de la cliente', 'url': reverse('fiche_cliente', args=[robe.client_id]), 'primary': True},
            ],
        },
    }


def _evenement_location(loc, kind):
    """kind : 'retrait' ou 'retour'."""
    robe = loc.robe_location
    sortie = loc.statut in ('EN_COURS', 'EN_RETARD', 'TERMINEE')  # la robe a déjà quitté l'atelier
    rendue = loc.statut == 'TERMINEE'
    en_retard = loc.est_en_retard or loc.statut == 'EN_RETARD'

    if kind == 'retrait':
        jour, libelle = loc.date_debut, 'Retrait'
        classes = ['ev', 'ev--retrait'] + (['ev--fait'] if sortie else [])
    else:
        jour, libelle = loc.date_fin_prevue, 'Retour'
        classes = ['ev', 'ev--retour']
        if rendue:
            classes.append('ev--fait')
        elif en_retard:
            classes.append('ev--retard')

    actions = [{'label': 'Dossier de la cliente', 'url': reverse('fiche_cliente', args=[loc.client_id])}]
    if not rendue and loc.statut != 'RESERVEE':
        actions.append({'label': 'Enregistrer le retour', 'url': reverse('retour_location', args=[loc.pk]), 'primary': True})

    return {
        'id': f'{kind}-{loc.pk}',
        'title': robe.nom_modele,
        'start': jour.isoformat(),
        'allDay': True,
        'classNames': classes,
        'extendedProps': {
            'kind': kind,
            'kind_label': libelle + (' en retard' if kind == 'retour' and en_retard and not rendue else ''),
            'client': _nom_cliente(loc.client),
            'telephone': loc.client.telephone or '',
            'lignes': [
                ['Cliente', _nom_cliente(loc.client)],
                ['Robe', f'{robe.nom_modele} ({robe.reference_stock}) · T.{robe.taille}'],
                ['Période', f'{_fmt(loc.date_debut)} → {_fmt(loc.date_fin_prevue)}'],
                ['Tarif convenu', f'{loc.prix_convenu} €'],
                ['Caution', f'{loc.caution_montant} € · {loc.get_caution_statut_display()}'],
                ['Contrat', f'n° {loc.pk} · {loc.get_statut_display()}'],
            ],
            'actions': actions,
        },
    }


@login_required
@require_GET
def api_planning_evenements(request):
    """Évènements entre `start` (inclus) et `end` (exclu), au format FullCalendar."""
    try:
        debut = _jour(request.GET.get('start'))
        fin = _jour(request.GET.get('end'))
    except ValueError:
        return JsonResponse({'error': "Paramètres 'start' et 'end' requis (AAAA-MM-JJ)."}, status=400)

    if fin <= debut or (fin - debut).days > DUREE_MAX_JOURS:
        return JsonResponse({'error': 'Période invalide.'}, status=400)

    aujourdhui = timezone.localdate()
    evenements = []

    robes = (Robe.objects
             .filter(date_livraison__gte=debut, date_livraison__lt=fin)
             .select_related('client')
             .prefetch_related('taches'))
    evenements += [_evenement_livraison(r, aujourdhui) for r in robes]

    actives = Location.objects.exclude(statut='ANNULEE').select_related('client', 'robe_location')

    for loc in actives.filter(date_debut__gte=debut, date_debut__lt=fin):
        evenements.append(_evenement_location(loc, 'retrait'))
    for loc in actives.filter(date_fin_prevue__gte=debut, date_fin_prevue__lt=fin):
        evenements.append(_evenement_location(loc, 'retour'))

    return JsonResponse(evenements, safe=False)
