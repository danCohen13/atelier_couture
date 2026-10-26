"""Variables disponibles dans tous les gabarits."""
from django.conf import settings


def atelier_courant(request):
    return {
        'atelier_courant': getattr(request, 'atelier', None),
        'PRODUIT_NOM': settings.PRODUIT_NOM,
    }
