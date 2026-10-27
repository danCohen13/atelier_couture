import json

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .acces import atelier_requis
from .forms import ClientForm, RobeForm
from .models import Client, Robe, Tache
from .services.extraction import extraire_mesures
from .services.gemini import ErreurIA
from .services.pdf import reponse_pdf

# ==============================================================================
# Vues Confection & Atelier
# ==============================================================================

@atelier_requis
def dashboard(request):
    all_robes = Robe.objects.de(request.atelier).select_related('client').prefetch_related('taches')
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

@atelier_requis
def fiche_cliente(request, client_id):
    cliente = get_object_or_404(Client.objects.de(request.atelier), id=client_id)
    robes = cliente.robes.prefetch_related('taches').all().order_by('-date_livraison')
    return render(request, 'atelier/confection/fiche_cliente.html', {'cliente': cliente, 'robes': robes})

@atelier_requis
def exporter_pdf_cliente(request, client_id):
    """Permet de sélectionner les robes à inclure et de télécharger la fiche PDF."""
    cliente = get_object_or_404(Client.objects.de(request.atelier), id=client_id)
    
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
        
        return reponse_pdf(request, 'atelier/pdf/fiche_cliente.html', context,
                           f"Recapitulatif_{cliente.nom}_{cliente.prenom}.pdf", 'fiche_cliente')

    robes = cliente.robes.all()
    return render(request, 'atelier/pdf/selection_robes.html', {'client': cliente, 'robes': robes})

@atelier_requis
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.atelier = request.atelier
            cliente.save()
            return redirect('dashboard')
    else:
        form = ClientForm()
    return render(request, 'atelier/confection/ajouter_client.html', {'form': form})

@atelier_requis
def ajouter_robe(request):
    client_id = request.GET.get('client_id')
    initial_data = {}
    
    if client_id:
        cliente = get_object_or_404(Client.objects.de(request.atelier), id=client_id)
        initial_data['client'] = cliente.id

    if request.method == 'POST':
        form = RobeForm(request.POST, request.FILES, atelier=request.atelier)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = RobeForm(initial=initial_data, atelier=request.atelier)

    return render(request, 'atelier/confection/ajouter_robe.html', {
        'form': form,
    })

@atelier_requis
def modifier_client(request, client_id):
    cliente = get_object_or_404(Client.objects.de(request.atelier), id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('fiche_cliente', client_id=cliente.id)
    else:
        form = ClientForm(instance=cliente)
    return render(request, 'atelier/confection/modifier_client.html', {'form': form, 'cliente': cliente})

@atelier_requis
def modifier_robe(request, robe_id):
    robe = get_object_or_404(Robe.objects.de(request.atelier), id=robe_id)
    if request.method == 'POST':
        form = RobeForm(request.POST, request.FILES, instance=robe, atelier=request.atelier)
        if form.is_valid():
            form.save()
            referer = request.META.get('HTTP_REFERER', '')
            if 'clientes' in referer:
                return redirect(f"{reverse('fiche_cliente', args=[robe.client.id])}#tiroir-{robe.id}")
            return redirect('dashboard')
    else:
        form = RobeForm(instance=robe, atelier=request.atelier)
    return render(request, 'atelier/confection/modifier_robe.html', {'form': form, 'robe': robe})    

@atelier_requis
@require_POST
def ajouter_tache_rapide(request, robe_id, type_tache):
    robe = get_object_or_404(Robe.objects.de(request.atelier), id=robe_id)
    correspondances = {
        'toile': _("Toile d'essai"),
        'coupe': _("Coupe du tissu"),
        'assemblage': _("Assemblage & Piqûre"),
        'finitions': _("Finitions & Ourlet")
    }
    if type_tache in correspondances:
        Tache.objects.create(robe=robe, libelle=correspondances[type_tache], est_faite=False)
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f"{reverse('fiche_cliente', args=[robe.client.id])}#tiroir-{robe.id}")
    return redirect(f"{reverse('dashboard')}#tiroir-{robe.id}")

@atelier_requis
def ajouter_tache_personnalisee(request, robe_id):
    robe = get_object_or_404(Robe.objects.de(request.atelier), id=robe_id)
    if request.method == 'POST':
        texte_saisi = request.POST.get('libelle', '').strip()
        if texte_saisi:
            Tache.objects.create(robe=robe, libelle=texte_saisi, est_faite=False)
            
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f"{reverse('fiche_cliente', args=[robe.client.id])}#tiroir-{robe.id}")
    return redirect(f"{reverse('dashboard')}#tiroir-{robe.id}")

@atelier_requis
@require_POST
def toggle_tache(request, tache_id):
    tache = get_object_or_404(Tache.objects.de(request.atelier), id=tache_id)
    tache.est_faite = not tache.est_faite
    tache.save()
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f"{reverse('fiche_cliente', args=[tache.robe.client.id])}#tiroir-{tache.robe.id}")
    return redirect(f"{reverse('dashboard')}#tiroir-{tache.robe.id}")

@atelier_requis
@require_POST
def supprimer_tache(request, tache_id):
    tache = get_object_or_404(Tache.objects.de(request.atelier), id=tache_id)
    robe_id = tache.robe.id
    client_id = tache.robe.client.id
    tache.delete()
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'clientes' in referer:
        return redirect(f"{reverse('fiche_cliente', args=[client_id])}#tiroir-{robe_id}")
    return redirect(f"{reverse('dashboard')}#tiroir-{robe_id}")

@atelier_requis
@require_POST
def supprimer_robe(request, robe_id):
    robe = get_object_or_404(Robe.objects.de(request.atelier), id=robe_id)
    robe.delete()
    return redirect('dashboard')

@atelier_requis
def liste_clientes(request):
    query = request.GET.get('q', '').strip()
    if query:
        clientes = Client.objects.de(request.atelier).filter(Q(nom__icontains=query) | Q(prenom__icontains=query)).order_by('nom')
    else:
        clientes = Client.objects.de(request.atelier).order_by('nom')
    return render(request, 'atelier/confection/liste_clientes.html', {'clientes': clientes, 'search_query': query})

@atelier_requis
@require_POST
def analyser_mesures_ia(request):
    """Dictée vocale → mesures (JSON). Le travail est fait par services.extraction."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': _('Format JSON invalide')}, status=400)

    texte_mesures = data.get('texte', '').strip()
    if not texte_mesures:
        return JsonResponse({'error': _('Aucun texte fourni')}, status=400)

    try:
        return JsonResponse(extraire_mesures(texte_mesures))
    except ErreurIA as erreur:
        return JsonResponse({'error': erreur.message}, status=erreur.status)
