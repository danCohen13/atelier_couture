"""Configuration des URL du projet."""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # L'adresse de l'administration est réglable (variable ADMIN_URL) pour ne pas
    # exposer /admin/ en production.
    path(settings.ADMIN_URL, admin.site.urls),
    path('', include('atelier.urls')),  # La racine du site est l'application atelier
]
