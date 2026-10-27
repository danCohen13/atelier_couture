from django.utils.translation import gettext_lazy as _

"""Devises proposées partout où l'on saisit un montant."""

# Devises proposées partout où l'on saisit un montant (confections, locations, stock).
# Le shekel est la devise par défaut de l'atelier.
DEVISE_CHOICES = [
    ('ILS', _('₪ (Shekel)')),
    ('EUR', _('€ (Euro)')),
    ('USD', _('$ (Dollar)')),
]
SYMBOLES_DEVISE = {'ILS': '₪', 'EUR': '€', 'USD': '$'}
