"""Réglages des finances : dépenses récurrentes, taux de change et objectif mensuel."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .acces import atelier_requis
from .forms import DepenseRecurrenteForm, ParametresFinanceForm
from .models import DepenseRecurrente, ParametresFinance
from .services import comptabilite as compta


@atelier_requis
def depenses_recurrentes(request):
    if request.method == 'POST':
        form = DepenseRecurrenteForm(request.POST)
        if form.is_valid():
            recurrente = form.save(commit=False)
            recurrente.atelier = request.atelier
            recurrente.save()
            compta.generer_depenses_recurrentes(request.atelier)
            messages.success(request, _("Dépense récurrente enregistrée."))
            return redirect('depenses_recurrentes')
    else:
        form = DepenseRecurrenteForm(initial={'date_debut': timezone.localdate(), 'jour_du_mois': 1})
    return render(request, 'atelier/finances/recurrentes.html', {
        'form': form, 'recurrentes': DepenseRecurrente.objects.de(request.atelier),
    })


@atelier_requis
@require_POST
def basculer_depense_recurrente(request, pk):
    rec = get_object_or_404(DepenseRecurrente.objects.de(request.atelier), pk=pk)
    rec.actif = not rec.actif
    rec.save(update_fields=['actif'])
    return redirect('depenses_recurrentes')


@atelier_requis
@require_POST
def supprimer_depense_recurrente(request, pk):
    rec = get_object_or_404(DepenseRecurrente.objects.de(request.atelier), pk=pk)
    rec.delete()  # les écritures déjà créées sont conservées (lien mis à NULL)
    messages.success(request, _("Dépense récurrente supprimée (les écritures passées sont conservées)."))
    return redirect('depenses_recurrentes')


@atelier_requis
def parametres_finance(request):
    params = ParametresFinance.charger(request.atelier)
    if request.method == 'POST':
        form = ParametresFinanceForm(request.POST, instance=params)
        if form.is_valid():
            form.save()
            messages.success(request, _("Paramètres enregistrés."))
            return redirect('parametres_finance')
    else:
        form = ParametresFinanceForm(instance=params)
    return render(request, 'atelier/finances/parametres.html', {'form': form})
