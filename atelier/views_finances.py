from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from itertools import groupby
from datetime import date, timedelta
from .models import Robe, Transaction
from .forms import TransactionForm

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

MOIS_ABBR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
             "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


class LigneCompte:
    def __init__(self, date, type, categorie_label, designation, robe, montant, devise_symbole='₪', auto=False):
        self.date = date
        self.type = type
        self.categorie_label = categorie_label
        self.designation = designation
        self.robe = robe
        self.montant = montant
        self.devise_symbole = devise_symbole
        self.auto = auto

    def get_categorie_display(self):
        return self.categorie_label


def construire_serie_graphe(lignes, granularite):
    """
    Construit les séries recettes / dépenses pour le graphe, regroupées
    par semaine, mois ou année, sur une fenêtre glissante se terminant
    aujourd'hui (les périodes sans opération apparaissent à 0 plutôt que
    d'être omises, pour que la courbe reste lisible).
    """
    aujourdhui = timezone.now().date()

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


@login_required
def finances_view(request):
    periode = request.GET.get('periode', 'tout')
    aujourdhui = timezone.now().date()

    lignes = []

    # 1. Génération automatique des écritures issues des caractéristiques des robes
    #    Seul le tissu est une vraie dépense (argent réellement sorti de la
    #    poche). La main d'œuvre n'est ni une dépense ni une recette séparée
    #    : c'est juste une composante du prix facturé au client (recette),
    #    donc elle ne doit pas être comptée une deuxième fois ici — elle
    #    reste visible sur la fiche de la robe, mais sort du grand livre.
    for robe in Robe.objects.select_related('client').all():
        symbole = robe.symbole_devise
        if robe.cout_tissu:
            lignes.append(LigneCompte(
                robe.date_commencement, 'DEPENSE', 'Tissu (auto)',
                f"Tissu — {robe.nom_modele}", robe, robe.cout_tissu, symbole, auto=True
            ))
        if robe.prix_total:
            lignes.append(LigneCompte(
                robe.date_livraison, 'RECETTE', 'Paiement client (auto)',
                f"Facturation — {robe.nom_modele}", robe, robe.prix_total, symbole, auto=True
            ))

    # 2. Injection des écritures manuelles du grand livre des comptes
    for t in Transaction.objects.select_related('robe').all():
        lignes.append(LigneCompte(
            t.date, t.type, t.get_categorie_display(), t.designation, t.robe, t.montant, '₪', auto=False
        ))

    # 3. Données du graphe — calculées sur l'historique complet, indépendamment
    #    du filtre de période appliqué au grand livre ci-dessous.
    chart_data = {
        'semaine': construire_serie_graphe(lignes, 'semaine'),
        'mois': construire_serie_graphe(lignes, 'mois'),
        'annee': construire_serie_graphe(lignes, 'annee'),
    }

    # 4. Filtrage temporel (grand livre uniquement)
    if periode == 'jour':
        lignes = [l for l in lignes if l.date == aujourdhui]
    elif periode == 'mois':
        lignes = [l for l in lignes if l.date.year == aujourdhui.year and l.date.month == aujourdhui.month]
    elif periode == 'annee':
        lignes = [l for l in lignes if l.date.year == aujourdhui.year]

    # 5. Calculs des bilans de la période
    total_recettes = sum((l.montant for l in lignes if l.type == 'RECETTE'), 0)
    total_depenses = sum((l.montant for l in lignes if l.type == 'DEPENSE'), 0)
    benefice_net = total_recettes - total_depenses

    # 6. Tri chronologique inversé et regroupement par mois de calendrier
    lignes.sort(key=lambda l: l.date, reverse=True)
    groupes = [
        {'label': f"{MOIS_FR[mois - 1]} {annee}", 'lignes': list(lignes_du_mois)}
        for (annee, mois), lignes_du_mois in groupby(lignes, key=lambda l: (l.date.year, l.date.month))
    ]

    context = {
        'total_recettes': total_recettes,
        'total_depenses': total_depenses,
        'benefice_net': benefice_net,
        'groupes': groupes,
        'periode': periode,
        'chart_data': chart_data,
    }

    return render(request, 'atelier/finances/finances.html', context)


@login_required
def ajouter_transaction_view(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finances')
    else:
        form = TransactionForm(initial={'date': timezone.now().date(), 'type': 'DEPENSE'})

    return render(request, 'atelier/finances/ajouter_transaction.html', {'form': form})