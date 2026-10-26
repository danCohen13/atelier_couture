"""Contrôle d'accès : une page de l'application exige un compte connecté ET rattaché à un atelier actif."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Adhesion


def atelier_requis(vue):
    """Remplace `@login_required` sur toutes les vues métier.

    Renseigne `request.atelier` (l'atelier de l'utilisatrice) ; sans atelier, ou si l'atelier est
    suspendu, la page est refusée (403). Toute requête de la vue doit ensuite passer par
    `Modele.objects.de(request.atelier)`.
    """
    @wraps(vue)
    @login_required
    def enveloppe(request, *args, **kwargs):
        adhesion = Adhesion.objects.select_related('atelier').filter(user=request.user).first()
        if adhesion is None:
            return render(request, 'atelier/acces_refuse.html', {'motif': 'sans_atelier'}, status=403)
        if adhesion.atelier.est_suspendu:
            return render(request, 'atelier/acces_refuse.html', {'motif': 'suspendu'}, status=403)
        request.atelier = adhesion.atelier
        request.adhesion = adhesion
        return vue(request, *args, **kwargs)
    return enveloppe
