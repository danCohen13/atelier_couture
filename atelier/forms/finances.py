"""Formulaires des finances."""
from django import forms

from ..models import DepenseRecurrente, Paiement, ParametresFinance, Transaction
from .commun import date_field


class TransactionForm(forms.ModelForm):
    date = date_field("Date")

    class Meta:
        model = Transaction
        fields = ['type', 'montant', 'categorie', 'designation', 'date', 'justificatif']

        widgets = {
            'type': forms.RadioSelect(),
            'categorie': forms.Select(attrs={'class': 'field-input'}),
            'montant': forms.NumberInput(attrs={'class': 'field-input', 'placeholder': '0.00', 'step': '0.01', 'autofocus': True}),
            'designation': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Ex : Achat fils dorés, acompte…'}),
            'justificatif': forms.URLInput(attrs={'class': 'field-input', 'placeholder': 'Photo du ticket (facultatif)'}),
        }

    def clean_montant(self):
        montant = self.cleaned_data['montant']
        if montant <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return montant


class PaiementForm(forms.ModelForm):
    date = date_field("Date du paiement")

    class Meta:
        model = Paiement
        fields = ['montant', 'date', 'mode', 'note']
        widgets = {
            'montant': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01', 'placeholder': '0.00'}),
            'mode': forms.Select(attrs={'class': 'field-input'}),
            'note': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Acompte, solde…'}),
        }

    def clean_montant(self):
        montant = self.cleaned_data['montant']
        if montant <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return montant


class DepenseRecurrenteForm(forms.ModelForm):
    date_debut = date_field("À partir du")

    class Meta:
        model = DepenseRecurrente
        fields = ['designation', 'montant', 'categorie', 'jour_du_mois', 'date_debut']
        widgets = {
            'designation': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Loyer atelier, abonnement…'}),
            'montant': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'categorie': forms.Select(attrs={'class': 'field-input'}),
            'jour_du_mois': forms.NumberInput(attrs={'class': 'field-input', 'min': 1, 'max': 28}),
        }

    def clean_montant(self):
        montant = self.cleaned_data['montant']
        if montant <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return montant

    def clean_jour_du_mois(self):
        jour = self.cleaned_data['jour_du_mois']
        if not 1 <= jour <= 28:
            raise forms.ValidationError("Choisis un jour entre 1 et 28.")
        return jour


class ParametresFinanceForm(forms.ModelForm):
    class Meta:
        model = ParametresFinance
        fields = ['taux_eur', 'taux_usd', 'objectif_mensuel']
        widgets = {
            'taux_eur': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.0001', 'placeholder': 'ex : 4.0000'}),
            'taux_usd': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.0001', 'placeholder': 'ex : 3.7000'}),
            'objectif_mensuel': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01', 'placeholder': 'ex : 15000'}),
        }

    def clean(self):
        donnees = super().clean()
        for champ in ('taux_eur', 'taux_usd', 'objectif_mensuel'):
            v = donnees.get(champ)
            if v is not None and v <= 0:
                self.add_error(champ, "La valeur doit être positive.")
        return donnees
