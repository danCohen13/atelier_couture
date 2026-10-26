"""Formulaire robe sur mesure."""
from django import forms

from ..models import Client, Robe
from .commun import date_field


class RobeForm(forms.ModelForm):
    # On applique la même rigueur pour les deux dates de la robe
    date_commencement = date_field("Date de commencement")
    date_livraison = date_field("Date de livraison")

    class Meta:
        model = Robe
        exclude = ['atelier']  # tout le reste : client, nom, finances, images ; l'atelier vient de la cliente

    def __init__(self, *args, atelier=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Une robe ne peut être rattachée qu'à une cliente de SON atelier.
        self.fields['client'].queryset = Client.objects.de(atelier) if atelier else Client.objects.none()

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
