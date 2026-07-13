from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Client, Robe, Tache
from .forms import ClientForm, RobeForm

@login_required
def dashboard(request):
    all_robes = Robe.objects.prefetch_related('taches').all()
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
    if request.method == 'POST':
        form = RobeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = RobeForm()
    return render(request, 'atelier/confection/ajouter_robe.html', {'form': form})

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