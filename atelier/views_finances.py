"""Page Finances : bilan, saisie et correction des opérations, saisie rapide par IA."""
import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .acces import atelier_requis
from .forms import TransactionForm
from .models import Transaction
from .services import comptabilite as compta
from .services.extraction import extraire_operation
from .services.gemini import ErreurIA

PERIODES = ('jour', 'mois', 'annee', 'tout')


def lire_filtres(request):
    """Période et base de calcul demandées dans l'URL (valeurs inconnues ramenées au défaut)."""
    periode = request.GET.get('periode', 'tout')
    if periode not in PERIODES:
        periode = 'tout'
    base = 'ENCAISSE' if request.GET.get('base') == 'encaisse' else 'FACTURE'
    return periode, base


@atelier_requis
def finances_view(request):
    periode, base = lire_filtres(request)
    return render(request, 'atelier/finances/finances.html', compta.tableau_de_bord(request.atelier, periode, base, page=request.GET.get('page')))


@atelier_requis
def ajouter_transaction_view(request):
    """
    Deux formulaires sur la page :
      - saisie rapide (bouton « Analyser ») : l'IA lit la phrase libre et pré-remplit les
        champs du second formulaire, sans rien enregistrer ;
      - formulaire classique (bouton « Enregistrer ») : validation et sauvegarde.
    """
    contexte = {}

    if request.method == 'POST' and 'analyser' in request.POST:
        phrase = request.POST.get('texte_ia', '').strip()
        contexte['texte_ia'] = phrase
        initial = {'date': timezone.localdate(), 'type': 'DEPENSE'}
        if not phrase:
            contexte['erreur_ia'] = "Écris ou dicte d'abord l'opération à analyser."
        else:
            try:
                initial.update(extraire_operation(phrase, timezone.localdate()))
            except ErreurIA as erreur:
                contexte['erreur_ia'] = erreur.message
        form = TransactionForm(initial=initial)

    elif request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.atelier = request.atelier
            operation.save()
            return redirect('finances')

    else:
        form = TransactionForm(initial={'date': timezone.localdate(), 'type': 'DEPENSE'})

    contexte['form'] = form
    return render(request, 'atelier/finances/ajouter_transaction.html', contexte)


@atelier_requis
def modifier_transaction_view(request, pk):
    transaction = get_object_or_404(Transaction.objects.de(request.atelier), pk=pk)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, "Opération modifiée.")
            return redirect('finances')
    else:
        form = TransactionForm(instance=transaction)
    return render(request, 'atelier/finances/form_transaction.html', {'form': form, 'transaction': transaction})


@atelier_requis
@require_POST
def supprimer_transaction(request, pk):
    get_object_or_404(Transaction.objects.de(request.atelier), pk=pk).delete()
    messages.success(request, "Opération supprimée.")
    return redirect('finances')


@atelier_requis
@require_POST
def analyser_texte_ia(request):
    """Variante AJAX de la saisie rapide : renvoie les champs extraits au format JSON."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON invalide'}, status=400)

    phrase = data.get('phrase', '').strip()
    if not phrase:
        return JsonResponse({'error': 'Aucun texte fourni'}, status=400)

    try:
        champs = extraire_operation(phrase, timezone.localdate())
    except ErreurIA as erreur:
        return JsonResponse({'error': erreur.message}, status=erreur.status)

    if 'date' in champs:
        champs['date'] = champs['date'].isoformat()
    return JsonResponse(champs)
