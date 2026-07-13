from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from itertools import groupby
from .models import Client, Robe, Tache
from .forms import ClientForm, RobeForm, TransactionForm
from django.db.models import Q, Sum
from .models import Transaction

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


class LigneCompte:
    """
    Une ligne du grand livre des comptes.
    Peut représenter soit une Transaction manuelle réelle, soit une ligne
    déduite automatiquement des coûts déjà saisis sur une robe (tissu,
    main d'œuvre, prix facturé) — pour ne jamais avoir à ressaisir ces
    montants dans le module Finances.
    """
    def __init__(self, date, type, categorie_label, designation, robe, montant, devise_symbole='₪', auto=False):
        self.date = date
        self.type = type
        self.categorie_label = categorie_label
        self.designation = designation
        self.robe = robe
        self.montant = montant
        self.devise_symbole = devise_symbole
        self.auto = auto

    def get_categorie_display(self):
        return self.categorie_label

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

    return render(request, 'atelier/dashboard.html', {
        'robes': robes_list,
        'current_status': filtre_status,
        'current_tri': tri,
    })

@login_required
def fiche_cliente(request, client_id):
    cliente = get_object_or_404(Client, id=client_id)
    robes = cliente.robes.prefetch_related('taches').all().order_by('-date_livraison')
    return render(request, 'atelier/fiche_cliente.html', {'cliente': cliente, 'robes': robes})

@login_required
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ClientForm()
    return render(request, 'atelier/ajouter_client.html', {'form': form})

@login_required
def ajouter_robe(request):
    if request.method == 'POST':
        form = RobeForm(request.POST, request.FILES) # Ajout indispensable pour capter les uploads
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = RobeForm()
    return render(request, 'atelier/ajouter_robe.html', {'form': form})

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
    return render(request, 'atelier/modifier_client.html', {'form': form, 'cliente': cliente})

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
    return render(request, 'atelier/modifier_robe.html', {'form': form, 'robe': robe})    

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
    return render(request, 'atelier/liste_clientes.html', {'clientes': clientes, 'search_query': query})

@login_required
def finances_view(request):
    periode = request.GET.get('periode', 'tout')
    aujourdhui = timezone.now().date()

    lignes = []

    # 1. Lignes déduites automatiquement de chaque robe — le tissu, la façon
    #    et le prix facturé sont déjà connus dès la création de la robe,
    #    aucune ressaisie n'est nécessaire ici.
    for robe in Robe.objects.select_related('client').all():
        symbole = robe.symbole_devise
        if robe.cout_tissu:
            lignes.append(LigneCompte(
                robe.date_commencement, 'DEPENSE', 'Tissu (auto)',
                f"Tissu — {robe.nom_modele}", robe, robe.cout_tissu, symbole, auto=True
            ))
        if robe.cout_main_doeuvre:
            lignes.append(LigneCompte(
                robe.date_commencement, 'DEPENSE', "Façon (auto)",
                f"Main d'œuvre — {robe.nom_modele}", robe, robe.cout_main_doeuvre, symbole, auto=True
            ))
        if robe.prix_total:
            lignes.append(LigneCompte(
                robe.date_livraison, 'RECETTE', 'Paiement client (auto)',
                f"Facturation — {robe.nom_modele}", robe, robe.prix_total, symbole, auto=True
            ))

    # 2. Lignes saisies manuellement (fournitures, matériel, autres opérations
    #    non liées directement au coût d'une robe)
    for t in Transaction.objects.select_related('robe').all():
        lignes.append(LigneCompte(
            t.date, t.type, t.get_categorie_display(), t.designation, t.robe, t.montant, '₪', auto=False
        ))

    # 3. Filtre par période
    if periode == 'jour':
        lignes = [l for l in lignes if l.date == aujourdhui]
    elif periode == 'mois':
        lignes = [l for l in lignes if l.date.year == aujourdhui.year and l.date.month == aujourdhui.month]
    elif periode == 'annee':
        lignes = [l for l in lignes if l.date.year == aujourdhui.year]

    # 4. Totaux sur la période sélectionnée
    total_recettes = sum((l.montant for l in lignes if l.type == 'RECETTE'), 0)
    total_depenses = sum((l.montant for l in lignes if l.type == 'DEPENSE'), 0)
    benefice_net = total_recettes - total_depenses

    # 5. Tri antéchronologique puis regroupement par mois pour une lecture
    #    claire du grand livre (jour / mois / année).
    lignes.sort(key=lambda l: l.date, reverse=True)
    groupes = [
        {'label': f"{MOIS_FR[mois - 1]} {annee}", 'lignes': list(lignes_du_mois)}
        for (annee, mois), lignes_du_mois in groupby(lignes, key=lambda l: (l.date.year, l.date.month))
    ]

    context = {
        'total_recettes': total_recettes,
        'total_depenses': total_depenses,
        'benefice_net': benefice_net,
        'groupes': groupes,
        'periode': periode,
    }

    return render(request, 'atelier/finances.html', context)

@login_required
def ajouter_transaction_view(request):
    """Vue pour enregistrer rapidement une opération manuelle (fournitures, matériel, etc.)"""
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finances')
    else:
        form = TransactionForm(initial={'date': timezone.now().date(), 'type': 'DEPENSE'})

    return render(request, 'atelier/ajouter_transaction.html', {'form': form})