"""Administration de la plateforme (réservée à l'exploitante du service, pas aux ateliers)."""
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .invitations import envoyer_invitation, lien_invitation
from .models import (
    Adhesion,
    Atelier,
    Client,
    DepenseRecurrente,
    IncidentSecurite,
    Invitation,
    Location,
    Paiement,
    ParametresFinance,
    Robe,
    RobeLocation,
    Tache,
    Transaction,
)


@admin.register(Atelier)
class AtelierAdmin(admin.ModelAdmin):
    list_display = ('nom', 'statut', 'offre', 'cree_le')
    list_filter = ('statut', 'offre')
    search_fields = ('nom',)


class InvitationAdminForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ('email', 'nom_atelier')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    """Inviter une nouvelle atelier : le lien s'affiche UNE fois à la création (et part par e-mail)."""
    list_display = ('email', 'nom_atelier', 'etat', 'cree_le', 'expire_le', 'atelier')
    search_fields = ('email', 'nom_atelier')
    readonly_fields = ('cree_le', 'expire_le', 'utilisee_le', 'atelier')
    form = InvitationAdminForm

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('email', 'nom_atelier')
        return ('email', 'nom_atelier', 'cree_le', 'expire_le', 'utilisee_le', 'atelier')

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, 'email', 'nom_atelier') if obj else ()

    @admin.display(description="État")
    def etat(self, obj):
        if obj.utilisee_le:
            return "Utilisée"
        return "En attente" if obj.est_utilisable else "Expirée"

    def save_model(self, request, obj, form, change):
        if change:
            return
        invitation, jeton = Invitation.creer(obj.email, obj.nom_atelier)
        obj.__dict__.update(invitation.__dict__)  # l'objet affiché ensuite est celui qui vient d'être créé
        lien = lien_invitation(jeton)
        if envoyer_invitation(invitation, jeton):
            self.message_user(request, f"Invitation envoyée à {invitation.email}. Lien (affiché une seule fois) : {lien}")
        else:
            self.message_user(
                request, f"L'e-mail n'a pas pu partir. Transmettez ce lien vous-même (affiché une seule fois) : {lien}",
                messages.WARNING)


@admin.register(Adhesion)
class AdhesionAdmin(admin.ModelAdmin):
    list_display = ('user', 'atelier', 'role')
    list_filter = ('role', 'atelier')


class AdminParAtelier(admin.ModelAdmin):
    """Chaque ligne affiche et filtre son atelier."""
    list_filter = ('atelier',)

    def get_list_display(self, request):
        return ('__str__', 'atelier', *super().get_list_display(request)[1:])


@admin.register(Client)
class ClientAdmin(AdminParAtelier):
    search_fields = ('nom', 'prenom')


@admin.register(Robe)
class RobeAdmin(AdminParAtelier):
    pass


@admin.register(Tache)
class TacheAdmin(AdminParAtelier):
    pass


@admin.register(RobeLocation)
class RobeLocationAdmin(AdminParAtelier):
    list_display = ('reference_stock', 'atelier', 'nom_modele', 'taille', 'couleur', 'prix_location_defaut', 'statut_physique')
    list_filter = ('atelier', 'statut_physique', 'taille', 'couleur')
    search_fields = ('reference_stock', 'nom_modele')


@admin.register(Location)
class LocationAdmin(AdminParAtelier):
    list_display = ('id', 'atelier', 'client', 'robe_location', 'date_debut', 'date_fin_prevue', 'statut', 'caution_statut')
    list_filter = ('atelier', 'statut', 'caution_statut', 'date_debut')
    search_fields = ('client__nom', 'client__prenom', 'robe_location__reference_stock')


@admin.register(Paiement)
class PaiementAdmin(AdminParAtelier):
    pass


@admin.register(DepenseRecurrente)
class DepenseRecurrenteAdmin(AdminParAtelier):
    pass


@admin.register(Transaction)
class TransactionAdmin(AdminParAtelier):
    pass


@admin.register(ParametresFinance)
class ParametresFinanceAdmin(admin.ModelAdmin):
    list_display = ('atelier', 'taux_eur', 'taux_usd', 'objectif_mensuel')


@admin.register(IncidentSecurite)
class IncidentSecuriteAdmin(AdminParAtelier):
    list_display = ('date_constat', 'atelier', 'description', 'grave', 'signale_autorite_le')
    list_filter = ('atelier', 'grave')
