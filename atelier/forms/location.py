"""Formulaires de location et de stock."""
from django import forms

from ..models import Client, Location, RobeLocation
from .commun import date_field


class DeviseParDefautMixin:
    """La devise est facultative dans le formulaire : sans valeur, le shekel (défaut du modèle) s'applique."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['devise'].required = False


class RobeLocationForm(DeviseParDefautMixin, forms.ModelForm):
    def __init__(self, *args, atelier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.atelier = atelier
        self.fields['cout_revient'].required = False

    def clean_reference_stock(self):
        """La référence est unique DANS l'atelier (la contrainte de base ne voit pas ce champ du formulaire)."""
        reference = self.cleaned_data['reference_stock']
        doublons = RobeLocation.objects.de(self.atelier).filter(reference_stock=reference)
        if self.instance.pk:
            doublons = doublons.exclude(pk=self.instance.pk)
        if doublons.exists():
            raise forms.ValidationError("Une robe du stock porte déjà cette référence.")
        return reference

    def clean_cout_revient(self):
        return self.cleaned_data.get('cout_revient') or 0

    class Meta:
        model = RobeLocation
        fields = [
            'reference_stock', 'nom_modele', 'taille', 'couleur',
            'devise', 'prix_location_defaut', 'caution_defaut', 'cout_revient', 'statut_physique',
            'photo', 'description', 'etat_general'
        ]
        widgets = {
            'devise': forms.Select(attrs={'class': 'field-input'}),
            'reference_stock': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: LOC-042'}),
            'nom_modele': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: Modèle Aurore'}),
            'taille': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: 38'}),
            'couleur': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: Ivoire'}),
            'prix_location_defaut': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'caution_defaut': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'cout_revient': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'statut_physique': forms.Select(attrs={'class': 'field-input'}),
            'description': forms.Textarea(attrs={'class': 'field-input', 'rows': 3}),
            'etat_general': forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Notes sur l\'usure, petits accrocs passés...'}),
        }


class LocationForm(DeviseParDefautMixin, forms.ModelForm):
    date_debut = date_field("Date de retrait prévue")
    date_fin_prevue = date_field("Date de retour prévue")

    def __init__(self, *args, atelier=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Cliente et robe de stock : uniquement celles de l'atelier.
        self.fields['client'].queryset = Client.objects.de(atelier) if atelier else Client.objects.none()
        self.fields['robe_location'].queryset = (
            RobeLocation.objects.de(atelier) if atelier else RobeLocation.objects.none())

    class Meta:
        model = Location
        fields = [
            'client', 'robe_location', 'date_debut', 'date_fin_prevue',
            'devise', 'prix_convenu', 'caution_montant', 'caution_statut',
            'delai_tampon_jours', 'statut', 'etat_avant', 'notes'
        ]
        widgets = {
            'devise': forms.Select(attrs={'class': 'field-input'}),
            'client': forms.Select(attrs={'class': 'field-input'}),
            'robe_location': forms.Select(attrs={'class': 'field-input'}),
            'prix_convenu': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'caution_montant': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'caution_statut': forms.Select(attrs={'class': 'field-input'}),
            'delai_tampon_jours': forms.NumberInput(attrs={'class': 'field-input', 'min': 0}),
            'statut': forms.Select(attrs={'class': 'field-input'}),
            'etat_avant': forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Constat de départ et retouches éphémères convenues...'}),
            'notes': forms.Textarea(attrs={'class': 'field-input', 'rows': 2}),
        }


class RetourLocationForm(forms.ModelForm):
    """Formulaire allégé pour la restitution rapide et l'état des lieux au retour."""
    date_retour_effectif = date_field("Date de retour effective", required=False)

    class Meta:
        model = Location
        fields = ['date_retour_effectif', 'caution_statut', 'caution_retenue', 'etat_apres', 'notes']
        widgets = {
            'caution_statut': forms.Select(attrs={'class': 'field-input'}),
            'caution_retenue': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01', 'min': 0}),
            'etat_apres': forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Taches, réparations à prévoir, départ pressing...'}),
            'notes': forms.Textarea(attrs={'class': 'field-input', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['caution_retenue'].required = False

    def clean(self):
        donnees = super().clean()
        retenue = donnees.get('caution_retenue') or 0
        statut = donnees.get('caution_statut')
        caution = self.instance.caution_montant or 0
        if retenue < 0 or retenue > caution:
            self.add_error('caution_retenue', f"La somme retenue doit être comprise entre 0 et {caution}.")
        elif statut == 'ENCAISSEE_PARTIEL' and retenue <= 0:
            self.add_error('caution_retenue', "Indique la somme retenue sur la caution.")
        donnees['caution_retenue'] = retenue
        return donnees
