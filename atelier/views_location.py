from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import RobeLocation, Location, Client
from .forms import RobeLocationForm, LocationForm, RetourLocationForm


@login_required
def catalogue_location(request):
    """Affiche l'inventaire des robes de stock avec filtres simples."""
    statut_filter = request.GET.get('statut')
    query = request.GET.get('q')

    robes = RobeLocation.objects.all()
    if statut_filter:
        robes = robes.filter(statut_physique=statut_filter)
    if query:
        robes = robes.filter(nom_modele__icontains=query) | robes.filter(reference_stock__icontains=query)

    return render(request, 'atelier/location/catalogue.html', {
        'robes': robes,
        'statut_filter': statut_filter,
        'query': query,
    })


@login_required
def ajouter_robe_location(request):
    """Ajout d'une nouvelle pièce au stock louable."""
    if request.method == 'POST':
        form = RobeLocationForm(request.POST, request.FILES)
        if form.is_valid():
            robe = form.save()
            messages.success(request, f"La robe {robe.reference_stock} a été ajoutée au stock.")
            return redirect('catalogue_location')
    else:
        form = RobeLocationForm()

    return render(request, 'atelier/location/form_robe_stock.html', {
        'form': form,
        'titre': "Ajouter une robe au catalogue de location"
    })


@login_required
def tableau_bord_locations(request):
    """Vue d'ensemble opérationnelle : sorties en cours, retours attendus, réservations."""
    aujourdhui = timezone.now().date()
    
    locations_en_cours = Location.objects.filter(statut='EN_COURS').select_related('client', 'robe_location')
    locations_reservees = Location.objects.filter(statut='RESERVEE').select_related('client', 'robe_location').order_by('date_debut')
    retours_en_retard = [loc for loc in locations_en_cours if loc.est_en_retard]
    
    locations_terminees = Location.objects.filter(statut='TERMINEE').select_related('client', 'robe_location')[:10]

    return render(request, 'atelier/location/tableau_bord.html', {
        'locations_en_cours': locations_en_cours,
        'locations_reservees': locations_reservees,
        'retours_en_retard': retours_en_retard,
        'locations_terminees': locations_terminees,
        'aujourdhui': aujourdhui,
    })


@login_required
def creer_location(request):
    """Création d'un contrat avec préremplissage automatique si demandé depuis une fiche cliente ou robe."""
    client_id = request.GET.get('client_id')
    robe_id = request.GET.get('robe_id')

    initial_data = {}
    if client_id:
        initial_data['client'] = get_object_or_404(Client, pk=client_id)
    if robe_id:
        robe = get_object_or_404(RobeLocation, pk=robe_id)
        initial_data['robe_location'] = robe
        initial_data['prix_convenu'] = robe.prix_location_defaut
        initial_data['caution_montant'] = robe.caution_defaut

    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            messages.success(request, f"Contrat #{location.id} enregistré avec succès.")
            return redirect('tableau_bord_locations')
    else:
        form = LocationForm(initial=initial_data)

    return render(request, 'atelier/location/form_location.html', {
        'form': form,
        'titre': "Établir un nouveau contrat de location"
    })


@login_required
def enregistrer_retour_location(request, pk):
    """Enregistre le retour d'une robe, l'état après location et gère la caution."""
    location = get_object_or_404(Location, pk=pk)

    if request.method == 'POST':
        form = RetourLocationForm(request.POST, instance=location)
        if form.is_valid():
            loc = form.save(commit=False)
            if not loc.date_retour_effectif:
                loc.date_retour_effectif = timezone.now().date()
            loc.statut = 'TERMINEE'
            loc.save()
            messages.success(request, f"Retour validé pour la robe {loc.robe_location.reference_stock}.")
            return redirect('tableau_bord_locations')
    else:
        form = RetourLocationForm(instance=location, initial={
            'date_retour_effectif': timezone.now().date()
        })

    return render(request, 'atelier/location/form_retour.html', {
        'form': form,
        'location': location,
    })