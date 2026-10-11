import csv
import json
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from itertools import groupby
from datetime import date, timedelta
from .models import (DepenseRecurrente, Location, ParametresFinance, Paiement, Robe, SYMBOLES_DEVISE,
                     Transaction)
from .forms import DepenseRecurrenteForm, PaiementForm, ParametresFinanceForm, TransactionForm
from .services import comptabilite as compta
from .services.comptabilite import DEVISE_PRINCIPALE, LigneCompte, MOIS_FR
from .services.pdf import render_to_pdf
from .services.extraction import extraire_operation
from .services.gemini import ErreurIA

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


PERIODES = ('jour', 'mois', 'annee', 'tout')


def _parametres_liste(request):
    periode = request.GET.get('periode', 'tout')
    if periode not in PERIODES:
        periode = 'tout'
    base = 'ENCAISSE' if request.GET.get('base') == 'encaisse' else 'FACTURE'
    return periode, base


@login_required
def finances_view(request):
    periode, base = _parametres_liste(request)
    aujourdhui = timezone.localdate()
    params = ParametresFinance.charger()

    compta.generer_depenses_recurrentes(aujourdhui)
    toutes = compta.construire_lignes(base)

    # Graphe : historique complet, uniquement dans la devise de l'atelier.
    lignes_graphe = [l for l in toutes if l.devise == DEVISE_PRINCIPALE]
    chart_data = {g: construire_serie_graphe(lignes_graphe, g) for g in ('semaine', 'mois', 'annee')}

    lignes = compta.filtrer_periode(toutes, periode, aujourdhui)
    principal = compta.bilan(lignes, DEVISE_PRINCIPALE)
    autres_bilans = [compta.bilan(lignes, d) for d in sorted({l.devise for l in lignes} - {DEVISE_PRINCIPALE})]

    elements = compta.creances(aujourdhui)
    cautions = compta.cautions_a_suivre()

    lignes.sort(key=lambda l: l.date, reverse=True)
    groupes = [
        {'label': f"{MOIS_FR[mois - 1]} {annee}", 'lignes': list(lignes_du_mois)}
        for (annee, mois), lignes_du_mois in groupby(lignes, key=lambda l: (l.date.year, l.date.month))
    ]

    context = {
        'total_recettes': principal['recettes'],
        'total_depenses': principal['depenses'],
        'benefice_net': principal['benefice'],
        'devise_symbole': SYMBOLES_DEVISE[DEVISE_PRINCIPALE],
        'autres_bilans': autres_bilans,
        'total_global': compta.total_global(lignes, params) if autres_bilans else None,
        'groupes': groupes,
        'periode': periode,
        'base': base,
        'chart_data': chart_data,
        'comparaison': compta.comparaison_mensuelle(toutes, params, aujourdhui),
        'depenses_par_categorie': compta.repartition_depenses(lignes, params),
        'activites': compta.repartition_activites(lignes, params),
        'objectif': compta.objectif_mensuel(toutes, params, aujourdhui),
        'reste_a_encaisser': compta.somme_par_devise((e['devise'], e['reste']) for e in elements),
        'cautions_detenues': compta.somme_par_devise(
            (c['location'].devise, c['location'].caution_montant) for c in cautions),
        'previsionnel': compta.previsionnel(elements, aujourdhui),
        'alertes': compta.alertes(elements, cautions, aujourdhui),
        'parametres': params,
    }
    return render(request, 'atelier/finances/finances.html', context)


# ---------------------------------------------------------------- exports

def _lignes_de_la_requete(request):
    periode, base = _parametres_liste(request)
    compta.generer_depenses_recurrentes()
    lignes = compta.filtrer_periode(compta.construire_lignes(base), periode)
    return periode, base, lignes


@login_required
def exporter_csv(request):
    periode, base, lignes = _lignes_de_la_requete(request)
    reponse = HttpResponse(content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = f'attachment; filename="finances-{periode}-{timezone.localdate():%Y%m%d}.csv"'
    reponse.write('\ufeff')  # BOM : Excel reconnaît l'UTF-8 (accents, ₪)
    csv.writer(reponse, delimiter=';').writerows(compta.lignes_csv(lignes))
    return reponse


@login_required
def exporter_pdf_recapitulatif(request):
    periode, base, lignes = _lignes_de_la_requete(request)
    params = ParametresFinance.charger()
    lignes.sort(key=lambda l: l.date, reverse=True)
    contexte = {
        'periode_label': {'jour': "Aujourd'hui", 'mois': 'Ce mois-ci', 'annee': 'Cette année', 'tout': 'Tout'}[periode],
        'base_label': "Encaissé" if base == 'ENCAISSE' else "Facturé",
        'date_edition': timezone.localdate(),
        'bilans': [compta.bilan(lignes, d) for d in sorted({l.devise for l in lignes} | {DEVISE_PRINCIPALE})],
        'depenses_par_categorie': compta.repartition_depenses(lignes, params),
        'activites': compta.repartition_activites(lignes, params),
        'lignes': lignes,
    }
    reponse = render_to_pdf('atelier/pdf/recap_finances.html', contexte)
    if reponse is None:
        messages.error(request, "Le PDF n'a pas pu être généré.")
        return redirect('finances')
    reponse['Content-Disposition'] = f'inline; filename="recapitulatif-{periode}.pdf"'
    return reponse


# ---------------------------------------------------------------- paiements

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


# ---------------------------------------------------------------- documents PDF

MENTION_DOCUMENT = ("Document de gestion interne. Il ne remplace pas une facture fiscale officielle "
                    "(numérotation et mentions légales à établir selon la réglementation en vigueur).")


def _reponse_pdf(request, gabarit, contexte, nom):
    reponse = render_to_pdf(gabarit, contexte)
    if reponse is None:
        messages.error(request, "Le PDF n'a pas pu être généré.")
        return redirect('finances')
    reponse['Content-Disposition'] = f'inline; filename="{nom}.pdf"'
    return reponse


@login_required
def document_pdf(request, type_, pk, genre):
    if type_ not in ('robe', 'location') or genre not in ('devis', 'facture'):
        raise Http404
    dossier = _dossier(type_, pk)
    if type_ == 'robe':
        designation = f"Confection sur mesure — {dossier.nom_modele}"
        total = dossier.prix_total
        prefixe = 'R'
    else:
        stock = dossier.robe_location
        designation = (f"Location — {stock.nom_modele} (réf. {stock.reference_stock}), "
                       f"du {dossier.date_debut:%d/%m/%Y} au {dossier.date_fin_prevue:%d/%m/%Y}")
        total = dossier.prix_convenu
        prefixe = 'L'
    numero = f"{'D' if genre == 'devis' else 'F'}-{prefixe}{dossier.pk:05d}"
    contexte = {
        'genre': genre, 'titre': 'Devis' if genre == 'devis' else 'Facture', 'numero': numero,
        'date_edition': timezone.localdate(), 'client': dossier.client, 'designation': designation,
        'total': total, 'symbole': dossier.devise, 'paiements': dossier.paiements.all(),
        'paye': dossier.total_paye, 'reste': dossier.reste_a_payer,
        'caution': dossier.caution_montant if type_ == 'location' else None,
        'mention': MENTION_DOCUMENT,
    }
    return _reponse_pdf(request, 'atelier/pdf/document_finance.html', contexte, numero)


@login_required
def recu_paiement(request, paiement_id):
    paiement = get_object_or_404(Paiement.objects.select_related('robe__client', 'location__client', 'location__robe_location'), pk=paiement_id)
    cible = paiement.cible
    designation = (f"Confection sur mesure — {cible.nom_modele}" if paiement.robe_id
                   else f"Location — {cible.robe_location.nom_modele} ({cible.robe_location.reference_stock})")
    numero = f"RC-{paiement.pk:05d}"
    contexte = {
        'paiement': paiement, 'numero': numero, 'client': cible.client, 'designation': designation,
        'symbole': cible.devise, 'date_edition': timezone.localdate(),
        'reste': cible.reste_a_payer, 'mention': MENTION_DOCUMENT,
    }
    return _reponse_pdf(request, 'atelier/pdf/recu_paiement.html', contexte, numero)


# ---------------------------------------------------------------- dépenses récurrentes & réglages

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


# ---------------------------------------------------------------- saisie / correction des opérations

@login_required
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
            form.save()
            return redirect('finances')

    else:
        form = TransactionForm(initial={'date': timezone.localdate(), 'type': 'DEPENSE'})

    contexte['form'] = form
    return render(request, 'atelier/finances/ajouter_transaction.html', contexte)


@login_required
def modifier_transaction_view(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, "Opération modifiée.")
            return redirect('finances')
    else:
        form = TransactionForm(instance=transaction)
    return render(request, 'atelier/finances/form_transaction.html', {'form': form, 'transaction': transaction})


@login_required
@require_POST
def supprimer_transaction(request, pk):
    get_object_or_404(Transaction, pk=pk).delete()
    messages.success(request, "Opération supprimée.")
    return redirect('finances')


@login_required
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
