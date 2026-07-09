from django import forms
from .models import Client, Robe

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'  # Inclut tous les champs de la table Client
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Boucle automatique pour appliquer le style Tailwind sur chaque champ
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'})

class RobeForm(forms.ModelForm):
    class Meta:
        model = Robe
        fields = '__all__'
        widgets = {
            # On force le navigateur à afficher un vrai calendrier pour les dates
            'date_commencement': forms.DateInput(attrs={'type': 'date'}),
            'date_livraison': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'})