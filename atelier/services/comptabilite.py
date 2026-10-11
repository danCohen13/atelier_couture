"""Calculs comptables de l'atelier (aucune vue ici : fonctions pures, faciles à tester).

Principes
---------
* Base « facturé » (par défaut) : une robe est comptée à sa date de livraison, une location à sa
  date de retrait. Base « encaissé » : on compte les paiements réellement reçus, à leur date.
* La caution n'est jamais un revenu, sauf la part conservée (dégâts, perte) : elle devient un
  revenu à la date de retour.
* Les montants de plusieurs devises ne sont jamais additionnés tels quels : les totaux « globaux »
  passent par les taux renseignés dans les paramètres (un devise sans taux est signalée).
"""
from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from ..models import (
    DepenseRecurrente, Location, ParametresFinance, Paiement, Robe, RobeLocation,
    SYMBOLES_DEVISE, Transaction,
)

DEVISE_PRINCIPALE = 'ILS'
ZERO = Decimal('0')

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


class LigneCompte:
    def __init__(self, date, type, categorie_label, designation, robe, montant, devise=DEVISE_PRINCIPALE,
                 auto=False, source='autre', transaction=None, justificatif=''):
        self.date = date
        self.type = type
        self.categorie_label = categorie_label
        self.designation = designation
        self.robe = robe
        self.montant = montant
        self.devise = devise
        self.devise_symbole = SYMBOLES_DEVISE.get(devise, devise)
        self.auto = auto
        self.source = source            # 'confection' | 'location' | 'autre'
        self.transaction = transaction  # écriture manuelle d'origine (modifiable)
        self.justificatif = justificatif

    def get_categorie_display(self):
        return self.categorie_label


# --------------------------------------------------------------------------- dépenses récurrentes

def _mois_suivant(annee, mois):
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def generer_depenses_recurrentes(aujourdhui=None):
    """Crée les écritures manquantes des dépenses récurrentes jusqu'à aujourd'hui (idempotent)."""
    aujourdhui = aujourdhui or timezone.localdate()
    creees = 0
    with db_transaction.atomic():
        for rec in DepenseRecurrente.objects.filter(actif=True):
            existantes = set(rec.transactions.values_list('date', flat=True))
            annee, mois = rec.date_debut.year, rec.date_debut.month
            while (annee, mois) <= (aujourdhui.year, aujourdhui.month):
                jour = date(annee, mois, min(max(rec.jour_du_mois, 1), 28))
                if jour >= rec.date_debut and jour <= aujourdhui and jour not in existantes:
                    Transaction.objects.create(
                        type='DEPENSE', montant=rec.montant, categorie=rec.categorie,
                        designation=rec.designation, date=jour, recurrente=rec,
                    )
                    creees += 1
                annee, mois = _mois_suivant(annee, mois)
    return creees


# --------------------------------------------------------------------------- écritures

def construire_lignes(base='FACTURE'):
    """Toutes les écritures (automatiques + manuelles). base = 'FACTURE' ou 'ENCAISSE'."""
    lignes = []
    robes = Robe.objects.select_related('client').prefetch_related('paiements')
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

    contrats = (Location.objects.exclude(statut='ANNULEE')
                .select_related('client', 'robe_location').prefetch_related('paiements'))
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

    for t in Transaction.objects.select_related('robe'):
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


# --------------------------------------------------------------------------- conversion

def en_shekels(montant, devise, params):
    """Montant converti en ₪ ; None si la devise n'a pas de taux."""
    taux = params.taux(devise)
    return None if taux is None else (montant * taux).quantize(Decimal('0.01'))


def convertir_lignes(lignes, params):
    """[(ligne, montant_en_₪)] + liste des devises ignorées faute de taux."""
    converties, ignorees = [], set()
    for l in lignes:
        m = en_shekels(l.montant, l.devise, params)
        if m is None:
            ignorees.add(l.devise)
        else:
            converties.append((l, m))
    return converties, sorted(ignorees)


def total_global(lignes, params):
    """Bilan unique en ₪ (autres devises converties). 'incomplet' liste les devises sans taux."""
    converties, ignorees = convertir_lignes(lignes, params)
    rec = sum((m for l, m in converties if l.type == 'RECETTE'), ZERO)
    dep = sum((m for l, m in converties if l.type == 'DEPENSE'), ZERO)
    return {'recettes': rec, 'depenses': dep, 'benefice': rec - dep, 'incomplet': ignorees}


def somme_par_devise(couples):
    """[(devise, montant)] → liste [{'devise','symbole','montant'}] triée, sans les zéros."""
    cumul = {}
    for devise, montant in couples:
        cumul[devise] = cumul.get(devise, ZERO) + montant
    return [{'devise': d, 'symbole': SYMBOLES_DEVISE.get(d, d), 'montant': m}
            for d, m in sorted(cumul.items()) if m]


# --------------------------------------------------------------------------- comparaisons

def _bornes_mois(annee, mois):
    return date(annee, mois, 1)


def _mois_decale(annee, mois, decalage):
    total = annee * 12 + (mois - 1) + decalage
    return total // 12, total % 12 + 1


def comparaison_mensuelle(lignes, params, aujourdhui=None):
    """Mois courant vs mois précédent vs même mois l'an dernier (en ₪)."""
    aujourdhui = aujourdhui or timezone.localdate()
    converties, _ = convertir_lignes(lignes, params)
    cibles = [
        ('Ce mois-ci', (aujourdhui.year, aujourdhui.month)),
        ('Mois précédent', _mois_decale(aujourdhui.year, aujourdhui.month, -1)),
        ("Même mois l'an dernier", (aujourdhui.year - 1, aujourdhui.month)),
    ]
    res = []
    for label, (a, m) in cibles:
        rec = sum((x for l, x in converties if l.type == 'RECETTE' and (l.date.year, l.date.month) == (a, m)), ZERO)
        dep = sum((x for l, x in converties if l.type == 'DEPENSE' and (l.date.year, l.date.month) == (a, m)), ZERO)
        res.append({'label': label, 'mois': f"{MOIS_FR[m - 1]} {a}", 'recettes': rec,
                    'depenses': dep, 'benefice': rec - dep})
    courant = res[0]
    for r in res[1:]:
        r['evolution'] = variation(courant['recettes'], r['recettes'])
    return res


def variation(actuel, reference):
    """Évolution en % ; None si la référence est nulle."""
    if not reference:
        return None
    return ((actuel - reference) / reference * 100).quantize(Decimal('0.1'))


def repartition_depenses(lignes, params):
    """Dépenses par catégorie, en ₪, avec la part de chacune (%)."""
    converties, _ = convertir_lignes([l for l in lignes if l.type == 'DEPENSE'], params)
    cumul = OrderedDict()
    for l, m in converties:
        cumul[l.categorie_label] = cumul.get(l.categorie_label, ZERO) + m
    total = sum(cumul.values(), ZERO)
    return [{'categorie': c, 'montant': m, 'part': (m / total * 100).quantize(Decimal('0.1')) if total else ZERO}
            for c, m in sorted(cumul.items(), key=lambda kv: kv[1], reverse=True)]


def repartition_activites(lignes, params):
    """Recettes / dépenses / bénéfice : confection sur mesure vs location (en ₪)."""
    converties, _ = convertir_lignes(lignes, params)
    res = []
    for cle, label in (('confection', 'Confection sur mesure'), ('location', 'Location'), ('autre', 'Frais généraux')):
        rec = sum((m for l, m in converties if l.source == cle and l.type == 'RECETTE'), ZERO)
        dep = sum((m for l, m in converties if l.source == cle and l.type == 'DEPENSE'), ZERO)
        if rec or dep:
            res.append({'label': label, 'recettes': rec, 'depenses': dep, 'benefice': rec - dep})
    total = sum((a['recettes'] for a in res), ZERO) or sum((a['depenses'] for a in res), ZERO)
    for a in res:
        base = a['recettes'] if sum((x['recettes'] for x in res), ZERO) else a['depenses']
        a['part'] = (base / total * 100).quantize(Decimal('0.1')) if total else ZERO
    return res


def objectif_mensuel(lignes, params, aujourdhui=None):
    """Avancement du chiffre d'affaires du mois vers l'objectif fixé (None si pas d'objectif)."""
    if not params.objectif_mensuel:
        return None
    aujourdhui = aujourdhui or timezone.localdate()
    converties, _ = convertir_lignes(lignes, params)
    realise = sum((m for l, m in converties if l.type == 'RECETTE'
                   and (l.date.year, l.date.month) == (aujourdhui.year, aujourdhui.month)), ZERO)
    pct = (realise / params.objectif_mensuel * 100).quantize(Decimal('0.1'))
    return {'objectif': params.objectif_mensuel, 'realise': realise, 'pct': pct,
            'pct_barre': int(min(pct, Decimal('100'))), 'atteint': realise >= params.objectif_mensuel}


# --------------------------------------------------------------------------- créances & cautions

def creances(aujourdhui=None):
    """Sommes restant à encaisser (robes et locations non annulées), avec retard éventuel."""
    aujourdhui = aujourdhui or timezone.localdate()
    elements = []
    for robe in Robe.objects.select_related('client').prefetch_related('paiements'):
        reste = robe.reste_a_payer
        if robe.prix_total and reste > 0:
            elements.append({
                'type': 'robe', 'objet': robe, 'libelle': robe.nom_modele, 'client': robe.client,
                'devise': robe.devise, 'symbole': robe.symbole_devise, 'total': robe.prix_total,
                'paye': robe.total_paye, 'reste': reste, 'echeance': robe.date_livraison,
                'en_retard': robe.date_livraison < aujourdhui,
            })
    for loc in (Location.objects.exclude(statut='ANNULEE').select_related('client', 'robe_location')
                .prefetch_related('paiements')):
        reste = loc.reste_a_payer
        if loc.prix_convenu and reste > 0:
            elements.append({
                'type': 'location', 'objet': loc, 'libelle': f"{loc.robe_location.nom_modele} ({loc.robe_location.reference_stock})",
                'client': loc.client, 'devise': loc.devise, 'symbole': loc.symbole_devise,
                'total': loc.prix_convenu, 'paye': loc.total_paye, 'reste': reste, 'echeance': loc.date_debut,
                'en_retard': loc.date_debut < aujourdhui,
            })
    elements.sort(key=lambda e: e['echeance'])
    return elements


def cautions_a_suivre():
    """Cautions détenues (chèque / empreinte) : à restituer une fois la robe rentrée."""
    res = []
    for loc in (Location.objects.exclude(statut='ANNULEE').filter(caution_statut='ENREGISTREE')
                .select_related('client', 'robe_location')):
        res.append({'location': loc, 'a_restituer': bool(loc.date_retour_effectif) or loc.statut == 'TERMINEE'})
    res.sort(key=lambda c: (not c['a_restituer'], c['location'].date_fin_prevue))
    return res


def previsionnel(elements, aujourdhui=None):
    """Entrées d'argent attendues, par tranche d'échéance (sommes par devise)."""
    aujourdhui = aujourdhui or timezone.localdate()
    tranches = [('En retard', None, -1), ('Cette semaine', 0, 7), ('Dans le mois', 8, 30), ('Plus tard', 31, None)]
    res = []
    for label, mini, maxi in tranches:
        couples = []
        for e in elements:
            jours = (e['echeance'] - aujourdhui).days
            if label == 'En retard':
                ok = jours < 0
            else:
                ok = jours >= mini and (maxi is None or jours <= maxi)
            if ok:
                couples.append((e['devise'], e['reste']))
        res.append({'label': label, 'montants': somme_par_devise(couples)})
    return res


def alertes(elements, cautions, aujourdhui=None):
    aujourdhui = aujourdhui or timezone.localdate()
    liste = []
    en_retard = [e for e in elements if e['en_retard']]
    if en_retard:
        liste.append(f"{len(en_retard)} paiement(s) en retard à réclamer")
    a_restituer = [c for c in cautions if c['a_restituer']]
    if a_restituer:
        liste.append(f"{len(a_restituer)} caution(s) à restituer ou à régulariser")
    retards = Location.objects.filter(statut__in=['EN_COURS', 'EN_RETARD'], date_retour_effectif__isnull=True,
                                      date_fin_prevue__lt=aujourdhui).count()
    if retards:
        liste.append(f"{retards} robe(s) louée(s) pas encore rendue(s)")
    return liste


# --------------------------------------------------------------------------- rentabilité

def rentabilite_robes():
    """Bénéfice de chaque robe sur mesure = prix − tissu − frais rattachés ; gain horaire si heures saisies."""
    res = []
    for robe in (Robe.objects.select_related('client').prefetch_related('transactions')):
        frais = sum((t.montant for t in robe.transactions.all() if t.type == 'DEPENSE'), ZERO)
        benefice = (robe.prix_total or ZERO) - (robe.cout_tissu or ZERO) - frais
        heures = robe.heures_travail or ZERO
        res.append({
            'robe': robe, 'prix': robe.prix_total, 'tissu': robe.cout_tissu, 'frais': frais,
            'benefice': benefice, 'symbole': robe.symbole_devise, 'devise': robe.devise,
            'heures': heures,
            'gain_horaire': (benefice / heures).quantize(Decimal('0.01')) if heures else None,
        })
    res.sort(key=lambda r: r['robe'].date_livraison, reverse=True)
    return res


def rentabilite_stock():
    """Pour chaque robe du stock : revenus des locations (même devise), nombre de sorties, amortissement."""
    res = []
    for stock in RobeLocation.objects.prefetch_related('locations'):
        contrats = [c for c in stock.locations.all() if c.statut != 'ANNULEE' and c.devise == stock.devise]
        revenus = sum((c.prix_convenu + c.caution_gardee for c in contrats), ZERO)
        cout = stock.cout_revient or ZERO
        res.append({
            'stock': stock, 'nb_locations': len(contrats), 'revenus': revenus, 'cout_revient': cout,
            'solde': revenus - cout, 'symbole': stock.symbole_devise,
            'amortissement': (revenus / cout * 100).quantize(Decimal('0.1')) if cout else None,
            'amortie': bool(cout) and revenus >= cout,
        })
    res.sort(key=lambda r: r['revenus'], reverse=True)
    return res


# --------------------------------------------------------------------------- export

def _cellule_sure(valeur):
    """Neutralise l'injection de formules à l'ouverture dans Excel / Sheets."""
    texte = str(valeur)
    return "'" + texte if texte[:1] in ('=', '+', '-', '@', '\t', '\r') else texte


def lignes_csv(lignes):
    """En-tête + lignes triées (date décroissante) prêtes pour csv.writer."""
    sortie = [['Date', 'Type', 'Catégorie', 'Désignation', 'Robe', 'Montant', 'Devise', 'Origine']]
    for l in sorted(lignes, key=lambda x: x.date, reverse=True):
        sortie.append([
            l.date.strftime('%d/%m/%Y'), 'Recette' if l.type == 'RECETTE' else 'Dépense',
            _cellule_sure(l.categorie_label), _cellule_sure(l.designation),
            _cellule_sure(l.robe.nom_modele) if l.robe else '', f"{l.montant:.2f}", l.devise,
            'Automatique' if l.auto else 'Saisie manuelle',
        ])
    return sortie
