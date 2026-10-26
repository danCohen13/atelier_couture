"""Configuration des URL du projet.

  /                  page d'accueil publique, connexion, invitation (atelier.urls_publiques)
  /app/...           l'application, réservée aux comptes rattachés à un atelier (atelier.urls)
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # L'adresse de l'administration est réglable (variable ADMIN_URL) pour ne pas
    # exposer /admin/ en production.
    path(settings.ADMIN_URL, admin.site.urls),
    path('app/', include('atelier.urls')),
    path('', include('atelier.urls_publiques')),
]
