from django.urls import path
from django.contrib.auth import views as auth_views
from . import views_atelier
from . import views_finances

urlpatterns = [
    # --- RACINE & ATELIER (views_atelier) ---
    path('', views_atelier.dashboard, name='dashboard'),
    path('client/ajouter/', views_atelier.ajouter_client, name='ajouter_client'),
    path('robe/ajouter/', views_atelier.ajouter_robe, name='ajouter_robe'),
    path('robe/<int:robe_id>/tache-rapide/<str:type_tache>/', views_atelier.ajouter_tache_rapide, name='ajouter_tache_rapide'),
    path('robe/<int:robe_id>/tache-personnalisee/', views_atelier.ajouter_tache_personnalisee, name='ajouter_tache_personnalisee'),
    path('tache/<int:tache_id>/toggle/', views_atelier.toggle_tache, name='toggle_tache'),
    path('robe/<int:robe_id>/supprimer/', views_atelier.supprimer_robe, name='supprimer_robe'),
    path('clientes/', views_atelier.liste_clientes, name='liste_clientes'),
    path('clientes/<int:client_id>/', views_atelier.fiche_cliente, name='fiche_cliente'),
    path('tache/<int:tache_id>/supprimer/', views_atelier.supprimer_tache, name='supprimer_tache'),
    path('client/<int:client_id>/modifier/', views_atelier.modifier_client, name='modifier_client'),
    path('robe/<int:robe_id>/modifier/', views_atelier.modifier_robe, name='modifier_robe'),
    
    # --- MODULE FINANCES (views_finances) ---
    path('finances/', views_finances.finances_view, name='finances'),
    path('finances/ajouter/', views_finances.ajouter_transaction_view, name='ajouter_transaction'),
    
    # LA NOUVELLE ROUTE IA ICI : 
    # Elle pointe vers ta fonction d'analyse et permet d'appeler l'URL en AJAX depuis le template
    path('finances/analyser-ia/', views_finances.analyser_texte_ia, name='analyser_texte_ia'),
    
    # --- ÉCRANS DE SÉCURITÉ ---
    path('login/', auth_views.LoginView.as_view(template_name='atelier/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('client/analyser-mesures/', views_atelier.analyser_mesures_ia, name='analyser_mesures_ia'),

    # 1. Demande de code par email
    path('mot-de-passe-oublie/', 
         views_atelier.demander_code_reset, 
         name='demander_code_reset'),

    # 2. Saisie du code à 6 chiffres
    path('mot-de-passe-oublie/verification/', 
         views_atelier.verifier_code_reset, 
         name='verifier_code_reset'),

    # 3. Création du nouveau mot de passe
    path('mot-de-passe-oublie/nouveau/', 
         views_atelier.nouveau_mot_de_passe, 
         name='nouveau_mot_de_passe'),
]