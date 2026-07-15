import os
import json
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_POST
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

@login_required
@require_POST
def analyser_mesures_ia(request):
    """
    Reçoit une dictée vocale textuelle et extrait les mesures physiques de la cliente.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON invalide'}, status=400)

    texte_mesures = data.get('texte', '').strip()
    if not texte_mesures:
        return JsonResponse({'error': 'Aucun texte fourni'}, status=400)

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'Clé API Gemini manquante'}, status=500)

    # Prompt d'extraction spécialisé pour la couture
    prompt_systeme = """
    Tu es un assistant technique d'atelier de haute couture.
    Analyse les notes ou la dictée vocale de l'utilisateur et extrait les mesures corporelles de la cliente.
    
    Tu dois obligatoirement renvoyer UNIQUEMENT un objet JSON pur avec la structure suivante (si une mesure n'est pas mentionnée, mets null) :
    {
        "tour_poitrine": un nombre entier ou décimal,
        "tour_taille": un nombre entier ou décimal,
        "tour_hanches": un nombre entier ou décimal,
        "hauteur_buste": un nombre entier ou décimal,
        "longueur_robe": un nombre entier ou décimal
    }
    
    Exemples de termes équivalents :
    - "poitrine", "tour de poitrine", "buste" -> tour_poitrine
    - "taille", "tour de taille" -> tour_taille
    - "hanches", "tour de hanches", "fesses" -> tour_hanches
    - "hauteur buste", "longueur buste", "épaule à taille" -> hauteur_buste
    - "longueur robe", "longueur jupe", "hauteur totale" -> longueur_robe

    Ne fournis aucune explication, aucune balise de code markdown. Renvoie juste le dictionnaire JSON.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_systeme},
                {"text": f"Texte à analyser : {texte_mesures}"}
            ]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        resultat_ia = response.json()
        
        texte_reponse = resultat_ia['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if texte_reponse.startswith("```"):
            texte_reponse = texte_reponse.strip("```").strip("json").strip()

        donnees_mesures = json.loads(texte_reponse)
        return JsonResponse(donnees_mesures)

    except Exception as e:
        return JsonResponse({'error': f"Erreur d'analyse : {str(e)}"}, status=500)