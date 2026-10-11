from django import forms
from .models import Client, Robe, Transaction
from .models import DepenseRecurrente, ParametresFinance, Paiement
from .models import RobeLocation, Location

# --- Dates : format unique jj/mm/aaaa sur tout le site -----------------------
DATE_FR = '%d/%m/%Y'
DATE_FR_INPUTS = [DATE_FR]


def date_widget():
    """Champ texte jj/mm/aaaa, branché sur le sélecteur Flatpickr de base.html."""
    return forms.DateInput(
        format=DATE_FR,
        attrs={
            'class': 'field-input datepicker',
            'placeholder': 'jj/mm/aaaa',
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


class ClientForm(forms.ModelForm):
    # On configure la date de naissance pour accepter et afficher le format jj/mm/aaaa
    date_naissance = date_field("Date de naissance", required=False)

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
    date_commencement = date_field("Date de commencement")
    date_livraison = date_field("Date de livraison")

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
        self.fields['heures_travail'].required = False
        self.fields['heures_travail'].widget.attrs.update({'placeholder': '0', 'step': '0.5'})

        for field_name in ['cout_tissu', 'cout_main_doeuvre', 'prix_total']:
            # Le placeholder est visible dans tous les cas si le champ est vide
            self.fields[field_name].widget.attrs.update({'placeholder': '0.00'})
            
            # LA CORRECTION : On force la valeur initiale à None UNIQUEMENT s'il s'agit d'une NOUVELLE robe.
            # Si self.instance.pk existe, cela signifie qu'on modifie une robe : on laisse Django charger les vrais prix !
            if not self.instance.pk:
                self.initial[field_name] = None

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

class DeviseParDefautMixin:
    """La devise est facultative dans le formulaire : sans valeur, le shekel (défaut du modèle) s'applique."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['devise'].required = False


class RobeLocationForm(DeviseParDefautMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cout_revient'].required = False

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
