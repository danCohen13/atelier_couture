"""Devises proposées partout où l'on saisit un montant."""

# Devises proposées partout où l'on saisit un montant (confections, locations, stock).
# Le shekel est la devise par défaut de l'atelier.
DEVISE_CHOICES = [
    ('ILS', '₪ (Shekel)'),
    ('EUR', '€ (Euro)'),
    ('USD', '$ (Dollar)'),
]
SYMBOLES_DEVISE = {'ILS': '₪', 'EUR': '€', 'USD': '$'}
