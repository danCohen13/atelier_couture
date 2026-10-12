"""Créances, cautions à suivre, prévisionnel et alertes."""
from django.utils import timezone

from ...models import Location, Robe
from .conversion import somme_par_devise


def creances(aujourdhui=None):
    """Sommes restant à encaisser (robes et locations non annulées), avec retard éventuel."""
    aujourdhui = aujourdhui or timezone.localdate()
    elements = []
    for robe in Robe.objects.select_related('client').prefetch_related('paiements'):
        reste = robe.reste_a_payer
        if robe.prix_total and reste > 0:
            elements.append({
                'type': 'robe', 'objet': robe, 'libelle': robe.nom_modele, 'client': robe.client,
                'devise': robe.devise, 'symbole': robe.symbole_devise, 'total': robe.prix_total,
                'paye': robe.total_paye, 'reste': reste, 'echeance': robe.date_livraison,
                'en_retard': robe.date_livraison < aujourdhui,
            })
    for loc in (Location.objects.exclude(statut='ANNULEE').select_related('client', 'robe_location')
                .prefetch_related('paiements')):
        reste = loc.reste_a_payer
        if loc.prix_convenu and reste > 0:
            elements.append({
                'type': 'location', 'objet': loc, 'libelle': f"{loc.robe_location.nom_modele} ({loc.robe_location.reference_stock})",
                'client': loc.client, 'devise': loc.devise, 'symbole': loc.symbole_devise,
                'total': loc.prix_convenu, 'paye': loc.total_paye, 'reste': reste, 'echeance': loc.date_debut,
                'en_retard': loc.date_debut < aujourdhui,
            })
    elements.sort(key=lambda e: e['echeance'])
    return elements


def cautions_a_suivre():
    """Cautions détenues (chèque / empreinte) : à restituer une fois la robe rentrée."""
    res = []
    for loc in (Location.objects.exclude(statut='ANNULEE').filter(caution_statut='ENREGISTREE')
                .select_related('client', 'robe_location')):
        res.append({'location': loc, 'a_restituer': bool(loc.date_retour_effectif) or loc.statut == 'TERMINEE'})
    res.sort(key=lambda c: (not c['a_restituer'], c['location'].date_fin_prevue))
    return res


def previsionnel(elements, aujourdhui=None):
    """Entrées d'argent attendues, par tranche d'échéance (sommes par devise)."""
    aujourdhui = aujourdhui or timezone.localdate()
    tranches = [('En retard', None, -1), ('Cette semaine', 0, 7), ('Dans le mois', 8, 30), ('Plus tard', 31, None)]
    res = []
    for label, mini, maxi in tranches:
        couples = []
        for e in elements:
            jours = (e['echeance'] - aujourdhui).days
            if label == 'En retard':
                ok = jours < 0
            else:
                ok = jours >= mini and (maxi is None or jours <= maxi)
            if ok:
                couples.append((e['devise'], e['reste']))
        res.append({'label': label, 'montants': somme_par_devise(couples)})
    return res


def alertes(elements, cautions, aujourdhui=None):
    aujourdhui = aujourdhui or timezone.localdate()
    liste = []
    en_retard = [e for e in elements if e['en_retard']]
    if en_retard:
        liste.append(f"{len(en_retard)} paiement(s) en retard à réclamer")
    a_restituer = [c for c in cautions if c['a_restituer']]
    if a_restituer:
        liste.append(f"{len(a_restituer)} caution(s) à restituer ou à régulariser")
    retards = Location.objects.filter(statut__in=['EN_COURS', 'EN_RETARD'], date_retour_effectif__isnull=True,
                                      date_fin_prevue__lt=aujourdhui).count()
    if retards:
        liste.append(f"{retards} robe(s) louée(s) pas encore rendue(s)")
    return liste
