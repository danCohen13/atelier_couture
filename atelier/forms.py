from django import forms
from .models import Client, Robe

class ClientForm(forms.ModelForm):
    # On force explicitement le format texte jj/mm/aaaa et son acceptation par Django
    date_naissance = forms.DateField(
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'placeholder': 'jj/mm/aaaa'}),
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
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'field-input'})

class RobeForm(forms.ModelForm):
    class Meta:
        model = Robe
        fields = '__all__'
        widgets = {
            'date_commencement': forms.DateInput(attrs={'type': 'date'}),
            'date_livraison': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'field-input'})
            
        # Effacer les 0.0 initiaux pour qu'ils soient vides au clic, mais garder un placeholder
        for field_name in ['cout_tissu', 'cout_main_doeuvre', 'prix_total']:
            self.initial[field_name] = None
            self.fields[field_name].widget.attrs.update({'placeholder': '0.00'})