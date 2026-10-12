"""Conversion en shekels et sommes par devise."""
from decimal import Decimal

from ...models import SYMBOLES_DEVISE
from .base import ZERO


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
