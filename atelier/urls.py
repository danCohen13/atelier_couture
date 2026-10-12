from django.urls import path
from django.contrib.auth import views as auth_views
from . import views_atelier
from . import views_auth
from . import views_confidentialite
from . import views_finances
from . import views_location
from . import views_planning

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
    path('finances/operation/<int:pk>/modifier/', views_finances.modifier_transaction_view, name='modifier_transaction'),
    path('finances/operation/<int:pk>/supprimer/', views_finances.supprimer_transaction, name='supprimer_transaction'),
    path('finances/export.csv', views_finances.exporter_csv, name='exporter_csv'),
    path('finances/recapitulatif.pdf', views_finances.exporter_pdf_recapitulatif, name='exporter_pdf_recapitulatif'),
    path('finances/impayes/', views_finances.impayes_view, name='impayes'),
    path('finances/rentabilite/', views_finances.rentabilite_view, name='rentabilite'),
    path('finances/recurrentes/', views_finances.depenses_recurrentes, name='depenses_recurrentes'),
    path('finances/recurrentes/<int:pk>/basculer/', views_finances.basculer_depense_recurrente, name='basculer_depense_recurrente'),
    path('finances/recurrentes/<int:pk>/supprimer/', views_finances.supprimer_depense_recurrente, name='supprimer_depense_recurrente'),
    path('finances/parametres/', views_finances.parametres_finance, name='parametres_finance'),
    path('finances/robe/<int:robe_id>/paiements/', views_finances.paiements_robe, name='paiements_robe'),
    path('finances/location/<int:location_id>/paiements/', views_finances.paiements_location, name='paiements_location'),
    path('finances/paiement/<int:paiement_id>/supprimer/', views_finances.supprimer_paiement, name='supprimer_paiement'),
    path('finances/paiement/<int:paiement_id>/recu/', views_finances.recu_paiement, name='recu_paiement'),
    path('finances/document/<str:type_>/<int:pk>/<str:genre>.pdf', views_finances.document_pdf, name='document_pdf'),
    
    # --- ÉCRANS DE SÉCURITÉ ---
    path('login/', auth_views.LoginView.as_view(template_name='atelier/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('client/analyser-mesures/', views_atelier.analyser_mesures_ia, name='analyser_mesures_ia'),

    # 1. Demande de code par email
    path('mot-de-passe-oublie/', 
         views_auth.demander_code_reset, 
         name='demander_code_reset'),

    # 2. Saisie du code à 6 chiffres
    path('mot-de-passe-oublie/verification/', 
         views_auth.verifier_code_reset, 
         name='verifier_code_reset'),

    # 3. Création du nouveau mot de passe
    path('mot-de-passe-oublie/nouveau/', 
         views_auth.nouveau_mot_de_passe, 
         name='nouveau_mot_de_passe'),

     path('clientes/<int:client_id>/pdf/', views_atelier.exporter_pdf_cliente, name='exporter_pdf_cliente'),
]

urlpatterns += [
    # Espace Location
    path('location/catalogue/', views_location.catalogue_location, name='catalogue_location'),
    path('location/catalogue/ajouter/', views_location.ajouter_robe_location, name='ajouter_robe_location'),
    path('location/tableau-de-bord/', views_location.tableau_bord_locations, name='tableau_bord_locations'),
    path('location/nouveau/', views_location.creer_location, name='creer_location'),
    path('location/<int:pk>/retour/', views_location.enregistrer_retour_location, name='retour_location'),
]

urlpatterns += [
    # Planning mensuel (livraisons, retraits et retours de location)
    path('planning/', views_planning.planning, name='planning'),
    path('api/planning/evenements/', views_planning.api_planning_evenements, name='api_planning_evenements'),
]

urlpatterns += [
    # Protection de la vie privée des clientes
    path('confidentialite/', views_confidentialite.confidentialite, name='confidentialite'),
    path('confidentialite/fiche-information.pdf', views_confidentialite.fiche_information_pdf, name='confidentialite_fiche_pdf'),
    path('clientes/<int:client_id>/information-remise/', views_confidentialite.information_remise, name='information_remise'),
    path('clientes/<int:client_id>/supprimer/', views_confidentialite.supprimer_cliente, name='supprimer_cliente'),
]
