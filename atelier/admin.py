from django.contrib import admin
from .models import Client, Robe, Tache
from .models import RobeLocation, Location

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