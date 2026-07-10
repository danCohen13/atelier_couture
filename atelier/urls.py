from django.urls import path
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
]
