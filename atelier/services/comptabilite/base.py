"""Constantes et ligne comptable commune."""
from decimal import Decimal

from ...models import SYMBOLES_DEVISE

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
