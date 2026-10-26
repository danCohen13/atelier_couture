"""Variables disponibles dans tous les gabarits."""
from django.conf import settings

from .models import Adhesion


def atelier_courant(request):
    correspondance = getattr(request, 'resolver_match', None)
    route = (correspondance.route if correspondance else '') or ''
    atelier = getattr(request, 'atelier', None)
    utilisateur = getattr(request, 'user', None)
    if atelier is None and utilisateur is not None and utilisateur.is_authenticated:
        # Pages publiques (accueil) : l'en-tête reconnaît l'utilisatrice connectée. Les pages de
        # l'application ont déjà `request.atelier` (posé par @atelier_requis) : pas de requête de plus.
        adhesion = Adhesion.objects.select_related('atelier').filter(user=utilisateur).first()
        if adhesion is not None and not adhesion.atelier.est_suspendu:
            atelier = adhesion.atelier
    return {
        'atelier_courant': atelier,
        'section_finances': route.startswith('app/finances/'),
        'PRODUIT_NOM': settings.PRODUIT_NOM,
    }
