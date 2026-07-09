from django.contrib import admin
from .models import Client, Robe, Tache

# Enregistrement des modèles pour qu'ils apparaissent dans l'interface
admin.site.register(Client)
admin.site.register(Robe)
admin.site.register(Tache)