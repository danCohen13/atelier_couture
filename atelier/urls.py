from django.urls import path
from django.contrib.auth import views as auth_views  # <-- Import des outils d'authentification
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('client/ajouter/', views.ajouter_client, name='ajouter_client'),
    path('robe/ajouter/', views.ajouter_robe, name='ajouter_robe'),
    path('robe/<int:robe_id>/tache-rapide/<str:type_tache>/', views.ajouter_tache_rapide, name='ajouter_tache_rapide'),
    path('robe/<int:robe_id>/tache-personnalisee/', views.ajouter_tache_personnalisee, name='ajouter_tache_personnalisee'),
    path('tache/<int:tache_id>/toggle/', views.toggle_tache, name='toggle_tache'),
    path('robe/<int:robe_id>/supprimer/', views.supprimer_robe, name='supprimer_robe'),
    path('clientes/', views.liste_clientes, name='liste_clientes'),
    path('clientes/<int:client_id>/', views.fiche_cliente, name='fiche_cliente'),
    path('tache/<int:tache_id>/supprimer/', views.supprimer_tache, name='supprimer_tache'),
    
    # Écrans de sécurité
    path('login/', auth_views.LoginView.as_view(template_name='atelier/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path('client/<int:client_id>/modifier/', views.modifier_client, name='modifier_client'),
    path('robe/<int:robe_id>/modifier/', views.modifier_robe, name='modifier_robe'),
]