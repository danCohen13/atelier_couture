"""Écritures (automatiques et manuelles), période et bilan, dépenses récurrentes."""
from datetime import date

from django.utils import timezone

from ...models import SYMBOLES_DEVISE, DepenseRecurrente, Location, Robe, Transaction
from .base import DEVISE_PRINCIPALE, ZERO, LigneCompte


def _mois_suivant(annee, mois):
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def generer_depenses_recurrentes(atelier, aujourdhui=None):
    """Crée les écritures manquantes des dépenses récurrentes de l'atelier jusqu'à aujourd'hui (idempotent).

    Deux requêtes de lecture au total (récurrentes actives, écritures déjà créées), et une seule
    insertion groupée s'il manque quelque chose ; aucune écriture sinon.
    """
    aujourdhui = aujourdhui or timezone.localdate()
    actives = list(DepenseRecurrente.objects.de(atelier).filter(actif=True))
    if not actives:
        return 0
    deja = set(Transaction.objects.de(atelier).filter(recurrente__in=actives).values_list('recurrente_id', 'date'))
    a_creer = []
    for rec in actives:
        annee, mois = rec.date_debut.year, rec.date_debut.month
        while (annee, mois) <= (aujourdhui.year, aujourdhui.month):
            jour = date(annee, mois, min(max(rec.jour_du_mois, 1), 28))
            if rec.date_debut <= jour <= aujourdhui and (rec.pk, jour) not in deja:
                a_creer.append(Transaction(
                    type='DEPENSE', montant=rec.montant, categorie=rec.categorie,
                    designation=rec.designation, date=jour, recurrente=rec, atelier=atelier))
            annee, mois = _mois_suivant(annee, mois)
    if a_creer:
        Transaction.objects.bulk_create(a_creer)
    return len(a_creer)


def charger_dossiers(atelier):
    """Robes et contrats non annulés, avec clientes et paiements : chargés UNE fois par page
    puis partagés entre les calculs (écritures, créances, cautions, alertes)."""
    robes = list(Robe.objects.de(atelier).select_related('client').prefetch_related('paiements'))
    contrats = list(Location.objects.de(atelier).exclude(statut='ANNULEE')
                    .select_related('client', 'robe_location').prefetch_related('paiements'))
    return robes, contrats


def construire_lignes(atelier, base='FACTURE', robes=None, contrats=None):
    """Toutes les écritures (automatiques + manuelles). base = 'FACTURE' ou 'ENCAISSE'.
    `robes` et `contrats` : dossiers déjà chargés (sinon chargés ici)."""
    if robes is None or contrats is None:
        robes, contrats = charger_dossiers(atelier)
    lignes = []
    for robe in robes:
        if robe.cout_tissu:
            lignes.append(LigneCompte(
                robe.date_commencement, 'DEPENSE', 'Tissu (auto)', f"Tissu — {robe.nom_modele}",
                robe, robe.cout_tissu, robe.devise, auto=True, source='confection'))
        if base == 'ENCAISSE':
            for p in robe.paiements.all():
                lignes.append(LigneCompte(
                    p.date, 'RECETTE', 'Paiement client (auto)',
                    f"Encaissement — {robe.nom_modele} ({p.get_mode_display()})",
                    robe, p.montant, robe.devise, auto=True, source='confection'))
        elif robe.prix_total:
            lignes.append(LigneCompte(
                robe.date_livraison, 'RECETTE', 'Paiement client (auto)', f"Facturation — {robe.nom_modele}",
                robe, robe.prix_total, robe.devise, auto=True, source='confection'))

    for loc in contrats:
        stock = loc.robe_location
        etiquette = f"{stock.nom_modele} ({stock.reference_stock}) · {loc.client}"
        if base == 'ENCAISSE':
            for p in loc.paiements.all():
                lignes.append(LigneCompte(
                    p.date, 'RECETTE', 'Location de robe (auto)', f"Encaissement location — {etiquette}",
                    None, p.montant, loc.devise, auto=True, source='location'))
        elif loc.prix_convenu:
            lignes.append(LigneCompte(
                loc.date_debut, 'RECETTE', 'Location de robe (auto)', f"Location — {etiquette}",
                None, loc.prix_convenu, loc.devise, auto=True, source='location'))
        gardee = loc.caution_gardee
        if gardee:
            lignes.append(LigneCompte(
                loc.date_retour_effectif or loc.date_fin_prevue, 'RECETTE', 'Caution retenue (auto)',
                f"Caution conservée — {etiquette}", None, gardee, loc.devise, auto=True, source='location'))

    for t in Transaction.objects.de(atelier).select_related('robe'):
        if t.categorie in ('LOCATION_ROBE',):
            source = 'location'
        elif t.categorie in ('PAIEMENT_CLIENT', 'TISSU'):
            source = 'confection'
        else:
            source = 'autre'
        lignes.append(LigneCompte(
            t.date, t.type, t.get_categorie_display(), t.designation, t.robe, t.montant,
            DEVISE_PRINCIPALE, auto=False, source=source, transaction=t, justificatif=t.justificatif))
    return lignes


def filtrer_periode(lignes, periode, aujourdhui=None):
    aujourdhui = aujourdhui or timezone.localdate()
    if periode == 'jour':
        return [l for l in lignes if l.date == aujourdhui]
    if periode == 'mois':
        return [l for l in lignes if (l.date.year, l.date.month) == (aujourdhui.year, aujourdhui.month)]
    if periode == 'annee':
        return [l for l in lignes if l.date.year == aujourdhui.year]
    return list(lignes)


def bilan(lignes, devise):
    recettes = sum((l.montant for l in lignes if l.devise == devise and l.type == 'RECETTE'), ZERO)
    depenses = sum((l.montant for l in lignes if l.devise == devise and l.type == 'DEPENSE'), ZERO)
    return {'devise': devise, 'symbole': SYMBOLES_DEVISE.get(devise, devise),
            'recettes': recettes, 'depenses': depenses, 'benefice': recettes - depenses}
