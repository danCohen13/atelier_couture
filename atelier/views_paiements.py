"""Paiements reçus, impayés et rentabilité."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .acces import atelier_requis
from .forms import PaiementForm
from .models import Location, Paiement, Robe
from .services import comptabilite as compta


def _dossier(request, type_, pk):
    if type_ == 'robe':
        return get_object_or_404(Robe.objects.de(request.atelier).select_related('client').prefetch_related('paiements'), pk=pk)
    return get_object_or_404(
        Location.objects.de(request.atelier).select_related('client', 'robe_location').prefetch_related('paiements'), pk=pk)


def _paiements_vue(request, type_, pk):
    dossier = _dossier(request, type_, pk)
    prix = dossier.prix_total if type_ == 'robe' else dossier.prix_convenu
    if request.method == 'POST':
        form = PaiementForm(request.POST, instance=Paiement(**{'robe' if type_ == 'robe' else 'location': dossier}))
        if form.is_valid():
            if form.cleaned_data['montant'] > dossier.reste_a_payer:
                form.add_error('montant', _("Ce paiement dépasse le reste à payer (%(montant)s %(devise)s).") % {'montant': dossier.reste_a_payer, 'devise': dossier.symbole_devise})
            else:
                form.save()
                messages.success(request, _("Paiement enregistré."))
                return redirect(request.path)
    else:
        form = PaiementForm(initial={'date': timezone.localdate()})
    return render(request, 'atelier/finances/paiements.html', {
        'dossier': dossier, 'type': type_, 'prix': prix, 'form': form,
        'paiements': dossier.paiements.all(),
        'titre': dossier.nom_modele if type_ == 'robe' else f"{dossier.robe_location.nom_modele} ({dossier.robe_location.reference_stock})",
    })


@atelier_requis
def paiements_robe(request, robe_id):
    return _paiements_vue(request, 'robe', robe_id)


@atelier_requis
def paiements_location(request, location_id):
    return _paiements_vue(request, 'location', location_id)


@atelier_requis
@require_POST
def supprimer_paiement(request, paiement_id):
    paiement = get_object_or_404(Paiement.objects.de(request.atelier), pk=paiement_id)
    retour = ('paiements_robe', paiement.robe_id) if paiement.robe_id else ('paiements_location', paiement.location_id)
    paiement.delete()
    messages.success(request, _("Paiement supprimé."))
    return redirect(retour[0], retour[1])


@atelier_requis
def impayes_view(request):
    elements = compta.creances(request.atelier)
    cautions = compta.cautions_a_suivre(request.atelier)
    return render(request, 'atelier/finances/impayes.html', {
        'elements': elements,
        'cautions': cautions,
        'total_du': compta.somme_par_devise((e['devise'], e['reste']) for e in elements),
        'total_retard': compta.somme_par_devise((e['devise'], e['reste']) for e in elements if e['en_retard']),
        'previsionnel': compta.previsionnel(elements),
    })


@atelier_requis
def rentabilite_view(request):
    return render(request, 'atelier/finances/rentabilite.html', {
        'robes': compta.rentabilite_robes(request.atelier),
        'stock': compta.rentabilite_stock(request.atelier),
    })
