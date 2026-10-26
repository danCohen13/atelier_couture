"""Formulaires de l'application, regroupés par domaine (importables depuis `atelier.forms`)."""
from .ateliers import AtelierReglagesForm
from .clients import ClientForm
from .commun import DATE_FR, DATE_FR_INPUTS, date_field, date_widget
from .confection import RobeForm
from .finances import DepenseRecurrenteForm, PaiementForm, ParametresFinanceForm, TransactionForm
from .location import DeviseParDefautMixin, LocationForm, RetourLocationForm, RobeLocationForm

__all__ = [
    'AtelierReglagesForm', 'ClientForm', 'DATE_FR', 'DATE_FR_INPUTS', 'date_field', 'date_widget', 'RobeForm',
    'DepenseRecurrenteForm', 'PaiementForm', 'ParametresFinanceForm', 'TransactionForm',
    'DeviseParDefautMixin', 'LocationForm', 'RetourLocationForm', 'RobeLocationForm',
]
