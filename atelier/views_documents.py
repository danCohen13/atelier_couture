"""Exports (CSV, PDF récapitulatif) et documents PDF : devis, factures, reçus."""
import csv

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .acces import atelier_requis
from .models import Paiement, ParametresFinance
from .services import comptabilite as compta
from .services.comptabilite import DEVISE_PRINCIPALE
from .services.pdf import reponse_pdf
from .views_finances import lire_filtres
from .views_paiements import _dossier


def _lignes_de_la_requete(request):
    periode, base = lire_filtres(request)
    compta.generer_depenses_recurrentes(request.atelier)
    lignes = compta.filtrer_periode(compta.construire_lignes(request.atelier, base), periode)
    return periode, base, lignes


@atelier_requis
def exporter_csv(request):
    periode, base, lignes = _lignes_de_la_requete(request)
    reponse = HttpResponse(content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = f'attachment; filename="finances-{periode}-{timezone.localdate():%Y%m%d}.csv"'
    reponse.write('\ufeff')  # BOM : Excel reconnaît l'UTF-8 (accents, ₪)
    csv.writer(reponse, delimiter=';').writerows(compta.lignes_csv(lignes))
    return reponse


@atelier_requis
def exporter_pdf_recapitulatif(request):
    periode, base, lignes = _lignes_de_la_requete(request)
    params = ParametresFinance.charger(request.atelier)
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
    return reponse_pdf(request, 'atelier/pdf/recap_finances.html', contexte, f'recapitulatif-{periode}.pdf', 'finances')


MENTION_DOCUMENT = ("Document de gestion interne. Il ne remplace pas une facture fiscale officielle "
                    "(numérotation et mentions légales à établir selon la réglementation en vigueur).")


@atelier_requis
def document_pdf(request, type_, pk, genre):
    if type_ not in ('robe', 'location') or genre not in ('devis', 'facture'):
        raise Http404
    dossier = _dossier(request, type_, pk)
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
    return reponse_pdf(request, 'atelier/pdf/document_finance.html', contexte, f'{numero}.pdf', 'finances')


@atelier_requis
def recu_paiement(request, paiement_id):
    paiement = get_object_or_404(Paiement.objects.de(request.atelier).select_related('robe__client', 'location__client', 'location__robe_location'), pk=paiement_id)
    cible = paiement.cible
    designation = (f"Confection sur mesure — {cible.nom_modele}" if paiement.robe_id
                   else f"Location — {cible.robe_location.nom_modele} ({cible.robe_location.reference_stock})")
    numero = f"RC-{paiement.pk:05d}"
    contexte = {
        'paiement': paiement, 'numero': numero, 'client': cible.client, 'designation': designation,
        'symbole': cible.devise, 'date_edition': timezone.localdate(),
        'reste': cible.reste_a_payer, 'mention': MENTION_DOCUMENT,
    }
    return reponse_pdf(request, 'atelier/pdf/recu_paiement.html', contexte, f'{numero}.pdf', 'finances')
