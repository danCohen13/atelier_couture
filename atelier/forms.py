from django import forms
from .models import Client, Robe

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
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['date_commencement', 'date_livraison']:
                field.widget.attrs.update({'class': 'field-input'})
                
        for field_name in ['cout_tissu', 'cout_main_doeuvre', 'prix_total']:
            self.initial[field_name] = None
            self.fields[field_name].widget.attrs.update({'placeholder': '0.00'})