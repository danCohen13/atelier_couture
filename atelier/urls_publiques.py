"""Adresses publiques : accueil, connexion, invitation, mot de passe oublié, choix de la langue."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import langue, views_auth, views_invitation, views_publiques

urlpatterns = [
    path('', views_publiques.accueil, name='accueil'),
    path('demande-invitation/', views_publiques.demander_invitation, name='demander_invitation'),
    path('connexion/', auth_views.LoginView.as_view(template_name='atelier/login.html', redirect_authenticated_user=True), name='login'),
    path('deconnexion/', auth_views.LogoutView.as_view(next_page='accueil'), name='logout'),
    path('invitation/<str:jeton>/', views_invitation.accepter_invitation, name='accepter_invitation'),
    path('langue/', langue.changer_langue, name='changer_langue'),
    path('mot-de-passe-oublie/', views_auth.demander_code_reset, name='demander_code_reset'),
    path('mot-de-passe-oublie/verification/', views_auth.verifier_code_reset, name='verifier_code_reset'),
    path('mot-de-passe-oublie/nouveau/', views_auth.nouveau_mot_de_passe, name='nouveau_mot_de_passe'),
]
