import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .forms import ClientForm, RobeForm
from .models import Client, Robe, Tache
from .services.extraction import extraire_mesures
from .services.gemini import ErreurIA
from .services.pdf import render_to_pdf


# ==============================================================================
# Vues Confection & Atelier
# ==============================================================================

@login_required
def dashboard(request):
    all_robes = Robe.objects.select_related('client').prefetch_related('taches')
    filtre_status = request.GET.get('status', 'actifs')
    tri = request.GET.get('tri', 'urgence')
    
    robes_list = list(all_robes)

    # Filtrage basé sur les propriétés magiques du modèle
    if filtre_status == 'actifs':
        robes_list = [r for r in robes_list if r.progression < 100]
    elif filtre_status == 'termines':
        robes_list = [r for r in robes_list if r.progression == 100]

    # Tri mécanique
    if tri == 'urgence':
        robes_list.sort(key=lambda r: r.jours_restants if r.jours_restants is not None else 99999)
    elif tri == 'prix':
        robes_list.sort(key=lambda r: r.prix_total or 0, reverse=True)
    elif tri == 'modele':
        robes_list.sort(key=lambda r: r.nom_modele.lower())

    return render(request, 'atelier/confection/dashboard.html', {
        'robes': robes_list,
        'current_status': filtre_status,
        'current_tri': tri,
    })

@login_required
def fiche_cliente(request, client_id):
    cliente = get_object_or_404(Client, id=client_id)
    robes = cliente.robes.prefetch_related('taches').all().order_by('-date_livraison')
    return render(request, 'atelier/confection/fiche_cliente.html', {'cliente': cliente, 'robes': robes})

@login_required
def exporter_pdf_cliente(request, client_id):
    """Permet de sélectionner les robes à inclure et de télécharger la fiche PDF."""
    cliente = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        robe_ids = request.POST.getlist('robes')
        if robe_ids:
            robes = cliente.robes.filter(id__in=robe_ids)
        else:
            robes = cliente.robes.all()
            
        total_prix = sum(r.prix_total or 0 for r in robes)
        
        context = {
            'client': cliente,
            'robes': robes,
            'total_prix': total_prix,
        }
        
        response = render_to_pdf('atelier/pdf/fiche_cliente.html', context)
        if response:
            filename = f"Recapitulatif_{cliente.nom}_{cliente.prenom}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
            
        return HttpResponse("Erreur lors de la génération du PDF", status=500)

    robes = cliente.robes.all()
    return render(request, 'atelier/pdf/selection_robes.html', {'client': cliente, 'robes': robes})

@login_required
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ClientForm()
    return render(request, 'atelier/confection/ajouter_client.html', {'form': form})

@login_required
def ajouter_robe(request):
    client_id = request.GET.get('client_id')
    initial_data = {}
    
    if client_id:
        cliente = get_object_or_404(Client, id=client_id)
        initial_data['client'] = cliente.id

    if request.method == 'POST':
        form = RobeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = RobeForm(initial=initial_data)

    return render(request, 'atelier/confection/ajouter_robe.html', {
        'form': form,
    })

@login_required
def modifier_client(request, client_id):
    cliente = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('fiche_cliente', client_id=cliente.id)
    else:
        form = ClientForm(instance=cliente)
    return render(request, 'atelier/confection/modifier_client.html', {'form': form, 'cliente': cliente})

@login_required
def modifier_robe(request, robe_id):
    robe = get_object_or_404(Robe, id=robe_id)
    if request.method == 'POST':
        form = RobeForm(request.POST, request.FILES, instance=robe)
        if form.is_valid():
            form.save()
            referer = request.META.get('HTTP_REFERER', '')
            if 'clientes' in referer:
                return redirect(f'/clientes/{robe.client.id}/#tiroir-{robe.id}')
            return redirect('dashboard')
    else:
        form = RobeForm(instance=robe)
    return render(request, 'atelier/confection/modifier_robe.html', {'form': form, 'robe': robe})    

@login_required
def ajouter_tache_rapide(request, robe_id, type_tache):
    robe = get_object_or_404(Robe, id=robe_id)
    correspondances = {
        'toile': "Toile d'essai",
        'coupe': "Coupe du tissu",
        'assemblage': "Assemblage & Piqûre",
        'finitions': "Finitions & Ourlet"
    }
    if type_tache in correspondances:
        Tache.objects.create(robe=robe, libelle=correspondances[type_tache], est_faite=False)
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f'/clientes/{robe.client.id}/#tiroir-{robe.id}')
    return redirect(f'/#tiroir-{robe.id}')

@login_required
def ajouter_tache_personnalisee(request, robe_id):
    robe = get_object_or_404(Robe, id=robe_id)
    if request.method == 'POST':
        texte_saisi = request.POST.get('libelle', '').strip()
        if texte_saisi:
            Tache.objects.create(robe=robe, libelle=texte_saisi, est_faite=False)
            
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f'/clientes/{robe.client.id}/#tiroir-{robe.id}')
    return redirect(f'/#tiroir-{robe.id}')

@login_required
def toggle_tache(request, tache_id):
    tache = get_object_or_404(Tache, id=tache_id)
    tache.est_faite = not tache.est_faite
    tache.save()
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f'/clientes/{tache.robe.client.id}/#tiroir-{tache.robe.id}')
    return redirect(f'/#tiroir-{tache.robe.id}')

@login_required
def supprimer_tache(request, tache_id):
    tache = get_object_or_404(Tache, id=tache_id)
    robe_id = tache.robe.id
    client_id = tache.robe.client.id
    tache.delete()
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f'/clientes/{client_id}/#tiroir-{robe_id}')
    return redirect(f'/#tiroir-{robe_id}')

@login_required
def supprimer_robe(request, robe_id):
    robe = get_object_or_404(Robe, id=robe_id)
    robe.delete()
    return redirect('dashboard')

@login_required
def liste_clientes(request):
    query = request.GET.get('q', '').strip()
    if query:
        clientes = Client.objects.filter(Q(nom__icontains=query) | Q(prenom__icontains=query)).order_by('nom')
    else:
        clientes = Client.objects.all().order_by('nom')
    return render(request, 'atelier/confection/liste_clientes.html', {'clientes': clientes, 'search_query': query})

@login_required
@require_POST
def analyser_mesures_ia(request):
    """Dictée vocale → mesures (JSON). Le travail est fait par services.extraction."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON invalide'}, status=400)

    texte_mesures = data.get('texte', '').strip()
    if not texte_mesures:
        return JsonResponse({'error': 'Aucun texte fourni'}, status=400)

    try:
        return JsonResponse(extraire_mesures(texte_mesures))
    except ErreurIA as erreur:
        return JsonResponse({'error': erreur.message}, status=erreur.status)
