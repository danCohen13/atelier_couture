"""Briques communes aux formulaires : champs de date jj/mm/aaaa."""
from django import forms
from django.utils.translation import gettext_lazy as _

# --- Dates : format unique jj/mm/aaaa sur tout le site -----------------------
DATE_FR = '%d/%m/%Y'
DATE_FR_INPUTS = [DATE_FR]


def date_widget():
    """Champ texte jj/mm/aaaa, branché sur le sélecteur Flatpickr de base.html."""
    return forms.DateInput(
        format=DATE_FR,
        attrs={
            'class': 'field-input datepicker',
            'placeholder': _('jj/mm/aaaa'),
            'inputmode': 'numeric',
            'autocomplete': 'off',
        },
    )


def date_field(label, required=True):
    return forms.DateField(
        label=label,
        required=required,
        input_formats=DATE_FR_INPUTS,
        widget=date_widget(),
    )
