from django.contrib import admin

from .models import (
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

# Enregistrement des modèles pour qu'ils apparaissent dans l'interface
admin.site.register(Client)
admin.site.register(Robe)
admin.site.register(Tache)


@admin.register(RobeLocation)
class RobeLocationAdmin(admin.ModelAdmin):
    list_display = ('reference_stock', 'nom_modele', 'taille', 'couleur', 'prix_location_defaut', 'statut_physique')
    list_filter = ('statut_physique', 'taille', 'couleur')
    search_fields = ('reference_stock', 'nom_modele')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'robe_location', 'date_debut', 'date_fin_prevue', 'statut', 'caution_statut')
    list_filter = ('statut', 'caution_statut', 'date_debut')
    search_fields = ('client__nom', 'client__prenom', 'robe_location__reference_stock')

admin.site.register(Paiement)
admin.site.register(DepenseRecurrente)
admin.site.register(ParametresFinance)
admin.site.register(Transaction)


@admin.register(IncidentSecurite)
class IncidentSecuriteAdmin(admin.ModelAdmin):
    list_display = ('date_constat', 'description', 'grave', 'signale_autorite_le')
    list_filter = ('grave',)
