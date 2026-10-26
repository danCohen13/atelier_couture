"""Réglages de l'atelier par sa propriétaire."""
from django import forms

from ..models import Atelier


class AtelierReglagesForm(forms.ModelForm):
    class Meta:
        model = Atelier
        fields = ['nom', 'contact_confidentialite']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'field-input'}),
            'contact_confidentialite': forms.TextInput(attrs={
                'class': 'field-input', 'placeholder': 'contact@exemple.com ou +972…'}),
        }
