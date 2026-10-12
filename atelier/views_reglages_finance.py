"""Réglages des finances : dépenses récurrentes, taux de change et objectif mensuel."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DepenseRecurrenteForm, ParametresFinanceForm
from .models import DepenseRecurrente, ParametresFinance
from .services import comptabilite as compta


@login_required
def depenses_recurrentes(request):
    if request.method == 'POST':
        form = DepenseRecurrenteForm(request.POST)
        if form.is_valid():
            form.save()
            compta.generer_depenses_recurrentes()
            messages.success(request, "Dépense récurrente enregistrée.")
            return redirect('depenses_recurrentes')
    else:
        form = DepenseRecurrenteForm(initial={'date_debut': timezone.localdate(), 'jour_du_mois': 1})
    return render(request, 'atelier/finances/recurrentes.html', {
        'form': form, 'recurrentes': DepenseRecurrente.objects.all(),
    })


@login_required
@require_POST
def basculer_depense_recurrente(request, pk):
    rec = get_object_or_404(DepenseRecurrente, pk=pk)
    rec.actif = not rec.actif
    rec.save(update_fields=['actif'])
    return redirect('depenses_recurrentes')


@login_required
@require_POST
def supprimer_depense_recurrente(request, pk):
    rec = get_object_or_404(DepenseRecurrente, pk=pk)
    rec.delete()  # les écritures déjà créées sont conservées (lien mis à NULL)
    messages.success(request, "Dépense récurrente supprimée (les écritures passées sont conservées).")
    return redirect('depenses_recurrentes')


@login_required
def parametres_finance(request):
    params = ParametresFinance.charger()
    if request.method == 'POST':
        form = ParametresFinanceForm(request.POST, instance=params)
        if form.is_valid():
            form.save()
            messages.success(request, "Paramètres enregistrés.")
            return redirect('parametres_finance')
    else:
        form = ParametresFinanceForm(instance=params)
    return render(request, 'atelier/finances/parametres.html', {'form': form})
