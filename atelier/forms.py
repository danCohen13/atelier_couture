from django import forms
from .models import Client, Robe, Transaction
from .models import RobeLocation, Location

class ClientForm(forms.ModelForm):
    # On configure la date de naissance pour accepter et afficher le format jj/mm/aaaa
    date_naissance = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'class': 'field-input datepicker', 'placeholder': 'jj/mm/aaaa'}),
        required=False,
        label="Date de naissance"
    )

    class Meta:
        model = Client
        fields = '__all__'
        widgets = {
            'telephone': forms.TextInput(attrs={'placeholder': '+336... ou +972...'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'date_naissance':
                field.widget.attrs.update({'class': 'field-input'})

class RobeForm(forms.ModelForm):
    # On applique la même rigueur pour les deux dates de la robe
    date_commencement = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'class': 'field-input datepicker', 'placeholder': 'jj/mm/aaaa'}),
        label="Date de commencement"
    )
    date_livraison = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'class': 'field-input datepicker', 'placeholder': 'jj/mm/aaaa'}),
        label="Date de livraison"
    )

    class Meta:
        model = Robe
        fields = '__all__'  # Inclut automatiquement client, nom, finances ET les nouvelles images

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Application automatique des classes CSS sur les composants
        for field_name, field in self.fields.items():
            if field_name not in ['date_commencement', 'date_livraison']:
                field.widget.attrs.update({'class': 'field-input'})
                
        # 2. Sécurisation de la distinction entre CRÉATION et MODIFICATION
        for field_name in ['cout_tissu', 'cout_main_doeuvre', 'prix_total']:
            # Le placeholder est visible dans tous les cas si le champ est vide
            self.fields[field_name].widget.attrs.update({'placeholder': '0.00'})
            
            # LA CORRECTION : On force la valeur initiale à None UNIQUEMENT s'il s'agit d'une NOUVELLE robe.
            # Si self.instance.pk existe, cela signifie qu'on modifie une robe : on laisse Django charger les vrais prix !
            if not self.instance.pk:
                self.initial[field_name] = None

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'montant', 'categorie', 'designation', 'date']

        widgets = {
            'type': forms.RadioSelect(),
            'categorie': forms.Select(attrs={'class': 'field-input'}),
            'montant': forms.NumberInput(attrs={'class': 'field-input', 'placeholder': '0.00', 'step': '0.01', 'autofocus': True}),
            'designation': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Ex : Achat fils dorés, acompte…'}),
            'date': forms.TextInput(attrs={'class': 'datepicker field-input'}),
        }

class RobeLocationForm(forms.ModelForm):
    class Meta:
        model = RobeLocation
        fields = [
            'reference_stock', 'nom_modele', 'taille', 'couleur',
            'prix_location_defaut', 'caution_defaut', 'statut_physique',
            'photo', 'description', 'etat_general'
        ]
        widgets = {
            'reference_stock': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: LOC-042'}),
            'nom_modele': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: Modèle Aurore'}),
            'taille': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: 38'}),
            'couleur': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'ex: Ivoire'}),
            'prix_location_defaut': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'caution_defaut': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'statut_physique': forms.Select(attrs={'class': 'field-input'}),
            'description': forms.Textarea(attrs={'class': 'field-input', 'rows': 3}),
            'etat_general': forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Notes sur l\'usure, petits accrocs passés...'}),
        }


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = [
            'client', 'robe_location', 'date_debut', 'date_fin_prevue',
            'prix_convenu', 'caution_montant', 'caution_statut',
            'delai_tampon_jours', 'statut', 'etat_avant', 'notes'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'field-input'}),
            'robe_location': forms.Select(attrs={'class': 'field-input'}),
            'date_debut': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
            'date_fin_prevue': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
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
    class Meta:
        model = Location
        fields = ['date_retour_effectif', 'caution_statut', 'etat_apres', 'notes']
        widgets = {
            'date_retour_effectif': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
            'caution_statut': forms.Select(attrs={'class': 'field-input'}),
            'etat_apres': forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Taches, réparations à prévoir, départ pressing...'}),
            'notes': forms.Textarea(attrs={'class': 'field-input', 'rows': 2}),
        }