"""Comparaisons mensuelles, répartitions et objectif mensuel."""
from collections import OrderedDict
from decimal import Decimal

from django.utils import timezone

from .base import MOIS_FR, ZERO
from .conversion import convertir_lignes


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
