from django.shortcuts import render, redirect, get_object_or_404
from .models import Robe, Tache
from .forms import ClientForm, RobeForm
import datetime

# 1. Vue du Tableau de Bord Principal (avec Filtres et Tris)
def dashboard(request):
    # Récupération de toutes les robes et de leurs tâches en 1 seule requête SQL
    all_robes = Robe.objects.prefetch_related('taches').all()
    aujourdhui = datetime.date.today()
    
    # Récupération des choix de filtres depuis l'URL (avec valeurs par défaut)
    filtre_status = request.GET.get('status', 'actifs')  # actifs, termines, toutes
    tri = request.GET.get('tri', 'urgence')              # urgence, prix, modele
    
    # Étape A : Calcul des jours restants et de la progression en mémoire
    for robe in all_robes:
        if robe.date_livraison:
            delta = robe.date_livraison - aujourdhui
            robe.jours_restants = delta.days
        else:
            robe.jours_restants = None
            
        taches = robe.taches.all()
        total_taches = taches.count()
        if total_taches > 0:
            faites = taches.filter(est_faite=True).count()
            robe.progression = int((faites / total_taches) * 100)
        else:
            robe.progression = 0

    # Étape B : Conversion en liste Python pour filtrer facilement
    robes_list = list(all_robes)

    # Étape C : Application du filtre de Statut
    if filtre_status == 'actifs':
        # On ne garde que les robes qui ne sont pas encore à 100%
        robes_list = [r for r in robes_list if r.progression < 100]
    elif filtre_status == 'termines':
        # On ne garde que les robes complètement terminées
        robes_list = [r for r in robes_list if r.progression == 100]

    # Étape D : Application du Tri mécanique
    if tri == 'urgence':
        # Les délais les plus courts en premier. Si pas de date, on repousse à la fin (99999)
        robes_list.sort(key=lambda r: r.jours_restants if r.jours_restants is not None else 99999)
    elif tri == 'prix':
        # Du prix le plus cher au moins cher
        robes_list.sort(key=lambda r: r.prix_total or 0, reverse=True)
    elif tri == 'modele':
        # Tri alphabétique par nom de modèle
        robes_list.sort(key=lambda r: r.nom_modele.lower())

    # On renvoie les variables de statut actuel pour que le HTML sache quel bouton surligner
    context = {
        'robes': robes_list,
        'aujourdhui': aujourdhui,
        'current_status': filtre_status,
        'current_tri': tri,
    }
    return render(request, 'atelier/dashboard.html', context)

# 2. Vue pour ajouter une cliente depuis le front-end
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ClientForm()
    return render(request, 'atelier/ajouter_client.html', {'form': form})

# 3. Vue pour ajouter une robe depuis le front-end
def ajouter_robe(request):
    if request.method == 'POST':
        form = RobeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = RobeForm()
    return render(request, 'atelier/ajouter_robe.html', {'form': form})

# 4. Action rapide en 1 clic pour injecter une tâche prédéfinie
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
    return redirect(f'/#tiroir-{robe.id}')

# 5. Action pour ajouter une tâche personnalisée saisie au clavier
def ajouter_tache_personnalisee(request, robe_id):
    robe = get_object_or_404(Robe, id=robe_id)
    if request.method == 'POST':
        texte_saisi = request.POST.get('libelle', '').strip()
        if texte_saisi:
            Tache.objects.create(robe=robe, libelle=texte_saisi, est_faite=False)
    return redirect(f'/#tiroir-{robe.id}')

# 6. Inverser le statut d'une tâche (Cocher / Décocher)
def toggle_tache(request, tache_id):
    tache = get_object_or_404(Tache, id=tache_id)
    tache.est_faite = not tache.est_faite
    tache.save()
    return redirect(f'/#tiroir-{tache.robe.id}')