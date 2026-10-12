"""Paiements reçus, impayés et rentabilité."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PaiementForm
from .models import Location, Paiement, Robe
from .services import comptabilite as compta


def _dossier(type_, pk):
    if type_ == 'robe':
        return get_object_or_404(Robe.objects.select_related('client').prefetch_related('paiements'), pk=pk)
    return get_object_or_404(
        Location.objects.select_related('client', 'robe_location').prefetch_related('paiements'), pk=pk)


def _paiements_vue(request, type_, pk):
    dossier = _dossier(type_, pk)
    prix = dossier.prix_total if type_ == 'robe' else dossier.prix_convenu
    if request.method == 'POST':
        form = PaiementForm(request.POST, instance=Paiement(**{'robe' if type_ == 'robe' else 'location': dossier}))
        if form.is_valid():
            if form.cleaned_data['montant'] > dossier.reste_a_payer:
                form.add_error('montant', f"Ce paiement dépasse le reste à payer ({dossier.reste_a_payer} {dossier.symbole_devise}).")
            else:
                form.save()
                messages.success(request, "Paiement enregistré.")
                return redirect(request.path)
    else:
        form = PaiementForm(initial={'date': timezone.localdate()})
    return render(request, 'atelier/finances/paiements.html', {
        'dossier': dossier, 'type': type_, 'prix': prix, 'form': form,
        'paiements': dossier.paiements.all(),
        'titre': dossier.nom_modele if type_ == 'robe' else f"{dossier.robe_location.nom_modele} ({dossier.robe_location.reference_stock})",
    })


@login_required
def paiements_robe(request, robe_id):
    return _paiements_vue(request, 'robe', robe_id)


@login_required
def paiements_location(request, location_id):
    return _paiements_vue(request, 'location', location_id)


@login_required
@require_POST
def supprimer_paiement(request, paiement_id):
    paiement = get_object_or_404(Paiement, pk=paiement_id)
    retour = ('paiements_robe', paiement.robe_id) if paiement.robe_id else ('paiements_location', paiement.location_id)
    paiement.delete()
    messages.success(request, "Paiement supprimé.")
    return redirect(retour[0], retour[1])


@login_required
def impayes_view(request):
    elements = compta.creances()
    cautions = compta.cautions_a_suivre()
    return render(request, 'atelier/finances/impayes.html', {
        'elements': elements,
        'cautions': cautions,
        'total_du': compta.somme_par_devise((e['devise'], e['reste']) for e in elements),
        'total_retard': compta.somme_par_devise((e['devise'], e['reste']) for e in elements if e['en_retard']),
        'previsionnel': compta.previsionnel(elements),
    })


@login_required
def rentabilite_view(request):
    return render(request, 'atelier/finances/rentabilite.html', {
        'robes': compta.rentabilite_robes(),
        'stock': compta.rentabilite_stock(),
    })
