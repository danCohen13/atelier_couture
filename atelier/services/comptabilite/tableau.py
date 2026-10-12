"""Données de la page Finances."""
from itertools import groupby

from django.utils import timezone

from ...models import SYMBOLES_DEVISE, ParametresFinance
from ..graphiques import construire_serie_graphe
from .analyses import comparaison_mensuelle, objectif_mensuel, repartition_activites, repartition_depenses
from .base import DEVISE_PRINCIPALE, MOIS_FR
from .conversion import somme_par_devise, total_global
from .creances import alertes, cautions_a_suivre, creances, previsionnel
from .ecritures import bilan, construire_lignes, filtrer_periode, generer_depenses_recurrentes


def grouper_par_mois(lignes):
    """Lignes triées (récentes d'abord) puis regroupées par mois : [{'label', 'lignes'}]."""
    lignes = sorted(lignes, key=lambda l: l.date, reverse=True)
    return [
        {'label': f"{MOIS_FR[mois - 1]} {annee}", 'lignes': list(du_mois)}
        for (annee, mois), du_mois in groupby(lignes, key=lambda l: (l.date.year, l.date.month))
    ]


def tableau_de_bord(periode, base, aujourdhui=None):
    """Tout ce qu'affiche la page Finances (la vue n'a plus qu'à rendre ce dictionnaire)."""
    aujourdhui = aujourdhui or timezone.localdate()
    params = ParametresFinance.charger()

    generer_depenses_recurrentes(aujourdhui)
    toutes = construire_lignes(base)

    # Graphe : historique complet, uniquement dans la devise de l'atelier.
    lignes_graphe = [l for l in toutes if l.devise == DEVISE_PRINCIPALE]
    chart_data = {g: construire_serie_graphe(lignes_graphe, g) for g in ('semaine', 'mois', 'annee')}

    lignes = filtrer_periode(toutes, periode, aujourdhui)
    principal = bilan(lignes, DEVISE_PRINCIPALE)
    autres_bilans = [bilan(lignes, d) for d in sorted({l.devise for l in lignes} - {DEVISE_PRINCIPALE})]

    elements = creances(aujourdhui)
    cautions = cautions_a_suivre()

    return {
        'total_recettes': principal['recettes'],
        'total_depenses': principal['depenses'],
        'benefice_net': principal['benefice'],
        'devise_symbole': SYMBOLES_DEVISE[DEVISE_PRINCIPALE],
        'autres_bilans': autres_bilans,
        'total_global': total_global(lignes, params) if autres_bilans else None,
        'groupes': grouper_par_mois(lignes),
        'periode': periode,
        'base': base,
        'chart_data': chart_data,
        'comparaison': comparaison_mensuelle(toutes, params, aujourdhui),
        'depenses_par_categorie': repartition_depenses(lignes, params),
        'activites': repartition_activites(lignes, params),
        'objectif': objectif_mensuel(toutes, params, aujourdhui),
        'reste_a_encaisser': somme_par_devise((e['devise'], e['reste']) for e in elements),
        'cautions_detenues': somme_par_devise(
            (c['location'].devise, c['location'].caution_montant) for c in cautions),
        'previsionnel': previsionnel(elements, aujourdhui),
        'alertes': alertes(elements, cautions, aujourdhui),
        'parametres': params,
    }
