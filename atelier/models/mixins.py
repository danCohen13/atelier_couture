"""Comportements partagés par plusieurs modèles (pas de champ ici : aucune migration n'est nécessaire)."""
from decimal import Decimal

from .constantes import SYMBOLES_DEVISE


class AvecDevise:
    """Pour tout modèle qui a un attribut `devise` (code « ILS », « EUR » ou « USD »)."""

    @property
    def symbole_devise(self):
        return SYMBOLES_DEVISE.get(self.devise, '₪')


class AvecPaiements:
    """Pour un dossier qui se règle en plusieurs paiements : une commande sur mesure ou une location.

    La classe indique dans `CHAMP_PRIX` quel champ porte le prix à payer. Les paiements sont lus avec
    `self.paiements.all()` : avec `prefetch_related('paiements')`, aucune requête SQL supplémentaire.
    """
    CHAMP_PRIX = None

    @property
    def total_paye(self):
        """Somme des paiements déjà reçus."""
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def reste_a_payer(self):
        """Prix moins ce qui a déjà été payé (peut être négatif si la cliente a trop payé)."""
        return (getattr(self, self.CHAMP_PRIX) or Decimal('0')) - self.total_paye
