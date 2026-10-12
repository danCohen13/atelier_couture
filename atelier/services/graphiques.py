"""Séries du graphique « entré / dépensé » de la page Finances."""
from datetime import date, timedelta

from django.utils import timezone

MOIS_ABBR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
             "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


def construire_serie_graphe(lignes, granularite):
    """
    Construit les séries recettes / dépenses pour le graphe, regroupées
    par semaine, mois ou année, sur une fenêtre glissante se terminant
    aujourd'hui (les périodes sans opération apparaissent à 0 plutôt que
    d'être omises, pour que la courbe reste lisible).
    """
    aujourdhui = timezone.localdate()

    if granularite == 'semaine':
        cles = []
        for i in range(11, -1, -1):
            jour = aujourdhui - timedelta(weeks=i)
            annee, semaine, _ = jour.isocalendar()
            cles.append((annee, semaine))
        cle_de = lambda d: d.isocalendar()[:2]
        libelle_de = lambda cle: date.fromisocalendar(cle[0], cle[1], 1).strftime('%d/%m')
    elif granularite == 'annee':
        cles = [(aujourdhui.year - i,) for i in range(4, -1, -1)]
        cle_de = lambda d: (d.year,)
        libelle_de = lambda cle: str(cle[0])
    else:  # mois
        cles = []
        annee, mois = aujourdhui.year, aujourdhui.month
        for i in range(11, -1, -1):
            m = mois - i
            a = annee
            while m <= 0:
                m += 12
                a -= 1
            cles.append((a, m))
        cle_de = lambda d: (d.year, d.month)
        libelle_de = lambda cle: f"{MOIS_ABBR[cle[1] - 1]} {cle[0]}"

    recettes = {cle: 0.0 for cle in cles}
    depenses = {cle: 0.0 for cle in cles}
    cles_valides = set(cles)

    for ligne in lignes:
        cle = cle_de(ligne.date)
        if cle not in cles_valides:
            continue
        if ligne.type == 'RECETTE':
            recettes[cle] += float(ligne.montant)
        else:
            depenses[cle] += float(ligne.montant)

    return {
        'labels': [libelle_de(cle) for cle in cles],
        'recettes': [round(recettes[cle], 2) for cle in cles],
        'depenses': [round(depenses[cle], 2) for cle in cles],
    }
