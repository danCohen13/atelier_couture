"""Administration de la plateforme (réservée à l'exploitante du service, pas aux ateliers)."""
from django.contrib import admin

from .models import (
    Adhesion,
    Atelier,
    Client,
    DepenseRecurrente,
    IncidentSecurite,
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
