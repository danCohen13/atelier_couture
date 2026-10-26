"""Pages publiques (sans compte)."""
from django.shortcuts import render


def accueil(request):
    return render(request, 'atelier/accueil.html')
