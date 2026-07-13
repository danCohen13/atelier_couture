from django import forms
from .models import Client, Robe, Transaction

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