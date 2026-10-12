"""Rentabilité par robe sur mesure et par robe du stock."""
from decimal import Decimal

from ...models import Robe, RobeLocation
from .base import ZERO


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
