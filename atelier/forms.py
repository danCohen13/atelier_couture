from django import forms
from .models import Client, Robe

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        
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