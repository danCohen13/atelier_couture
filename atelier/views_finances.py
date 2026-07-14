from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from itertools import groupby
from .models import Robe, Transaction
from .forms import TransactionForm

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


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


@login_required
def finances_view(request):
    periode = request.GET.get('periode', 'tout')
    aujourdhui = timezone.now().date()

    lignes = []

    # 1. Génération automatique des écritures issues des caractéristiques des robes
    for robe in Robe.objects.select_related('client').all():
        symbole = robe.symbole_devise
        if robe.cout_tissu:
            lignes.append(LigneCompte(
                robe.date_commencement, 'DEPENSE', 'Tissu (auto)',
                f"Tissu — {robe.nom_modele}", robe, robe.cout_tissu, symbole, auto=True
            ))
        if robe.cout_main_doeuvre:
            lignes.append(LigneCompte(
                robe.date_commencement, 'DEPENSE', "Façon (auto)",
                f"Main d'œuvre — {robe.nom_modele}", robe, robe.cout_main_doeuvre, symbole, auto=True
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

    # 3. Filtrage temporel
    if periode == 'jour':
        lignes = [l for l in lignes if l.date == aujourdhui]
    elif periode == 'mois':
        lignes = [l for l in lignes if l.date.year == aujourdhui.year and l.date.month == aujourdhui.month]
    elif periode == 'annee':
        lignes = [l for l in lignes if l.date.year == aujourdhui.year]

    # 4. Calculs des bilans de la période
    total_recettes = sum((l.montant for l in lignes if l.type == 'RECETTE'), 0)
    total_depenses = sum((l.montant for l in lignes if l.type == 'DEPENSE'), 0)
    benefice_net = total_recettes - total_depenses

    # 5. Tri chronologique inversé et regroupement par mois de calendrier
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