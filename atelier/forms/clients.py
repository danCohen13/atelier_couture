"""Formulaire cliente."""
from django import forms

from ..models import Client
from .commun import date_field


class ClientForm(forms.ModelForm):
    # On configure la date de naissance pour accepter et afficher le format jj/mm/aaaa
    date_naissance = date_field("Date de naissance", required=False)
    information_remise_le = date_field("Fiche d'information remise le", required=False)

    class Meta:
        model = Client
        exclude = ['cree_le', 'anonymisee_le']
        widgets = {
            'telephone': forms.TextInput(attrs={'placeholder': '+972... ou +336...'}),
            'notes_morphologie': forms.Textarea(attrs={
                'rows': 3, 'placeholder': "Morphologie uniquement — pas d'information médicale"}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ('date_naissance', 'information_remise_le'):
                field.widget.attrs.update({'class': 'field-input'})
