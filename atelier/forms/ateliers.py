"""Réglages de l'atelier par sa propriétaire."""
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from ..models import Atelier


class AtelierReglagesForm(forms.ModelForm):
    class Meta:
        model = Atelier
        fields = ['nom', 'contact_confidentialite']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'field-input'}),
            'contact_confidentialite': forms.TextInput(attrs={
                'class': 'field-input', 'placeholder': _('contact@exemple.com ou +972…')}),
        }


class InscriptionForm(forms.Form):
    """Création du compte et de l'atelier à partir d'une invitation."""
    nom_atelier = forms.CharField(
        max_length=150, label=_("Nom de votre atelier"),
        widget=forms.TextInput(attrs={'class': 'field-input', 'autofocus': True}))
    identifiant = forms.CharField(
        max_length=150, label=_("Identifiant de connexion"),
        widget=forms.TextInput(attrs={'class': 'field-input', 'autocomplete': 'username'}))
    mot_de_passe = forms.CharField(
        label=_("Mot de passe"), strip=False,
        widget=forms.PasswordInput(attrs={'class': 'field-input', 'autocomplete': 'new-password'}))
    confirmation = forms.CharField(
        label=_("Confirmez le mot de passe"), strip=False,
        widget=forms.PasswordInput(attrs={'class': 'field-input', 'autocomplete': 'new-password'}))

    def __init__(self, *args, email='', **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email

    def clean_identifiant(self):
        identifiant = self.cleaned_data['identifiant'].strip()
        if User.objects.filter(username__iexact=identifiant).exists():
            raise forms.ValidationError(_("Cet identifiant est déjà pris."))
        return identifiant

    def clean(self):
        donnees = super().clean()
        mdp = donnees.get('mot_de_passe')
        if mdp and mdp != donnees.get('confirmation'):
            self.add_error('confirmation', _("Les deux mots de passe ne sont pas identiques."))
        elif mdp:
            # Les validateurs comparent le mot de passe à l'identifiant et à l'e-mail.
            try:
                validate_password(mdp, User(username=donnees.get('identifiant', ''), email=self.email))
            except forms.ValidationError as erreur:
                self.add_error('mot_de_passe', erreur)
        return donnees


class DemandeInvitationForm(forms.Form):
    """Formulaire de la page d'accueil. Le champ `site_web` est un piège à robots : invisible, il reste vide."""
    email = forms.EmailField(label=_("Votre adresse e-mail"), widget=forms.EmailInput(attrs={
        'autocomplete': 'email', 'dir': 'ltr'}))
    nom_atelier = forms.CharField(label=_("Nom de votre atelier"), max_length=150, required=False)
    site_web = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'tabindex': '-1', 'autocomplete': 'off', 'aria-hidden': 'true'}))

    def clean_site_web(self):
        if self.cleaned_data['site_web']:
            raise forms.ValidationError("")
        return ''
