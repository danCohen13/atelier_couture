"""Pages publiques (sans compte)."""
import logging

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import DemandeInvitationForm
from .models import DemandeInvitation

logger = logging.getLogger(__name__)

DEMANDES_MAX_PAR_HEURE = 5


def accueil(request):
    return render(request, 'atelier/accueil.html', {'form_demande': DemandeInvitationForm()})


def _adresse_ip(request):
    return request.META.get('REMOTE_ADDR', '')


@require_POST
def demander_invitation(request):
    """Enregistre une demande. La réponse est la même quelle que soit l'adresse (pas d'énumération)."""
    form = DemandeInvitationForm(request.POST)
    ancre = reverse('accueil') + '#demande'
    if not form.is_valid():
        if 'site_web' in form.errors:  # robot : on fait comme si tout allait bien
            messages.success(request, _("Merci ! Nous vous écrivons très vite avec votre invitation."))
        else:
            messages.error(request, _("Vérifiez votre adresse e-mail."))
        return redirect(ancre)

    cle = f'demandes:{_adresse_ip(request)}'
    cache.add(cle, 0, timeout=3600)
    if cache.incr(cle) > DEMANDES_MAX_PAR_HEURE:
        messages.error(request, _("Trop de demandes depuis cette connexion. Réessayez plus tard."))
        return redirect(ancre)

    email = form.cleaned_data['email'].strip()
    nom = form.cleaned_data['nom_atelier'].strip()
    if not DemandeInvitation.objects.filter(email__iexact=email, traitee=False).exists():
        DemandeInvitation.objects.create(email=email, nom_atelier=nom)
        destinataire = getattr(settings, 'NOTIFIER_DEMANDES_A', '')
        if destinataire:
            try:
                send_mail(f"Nouvelle demande d'invitation — {settings.PRODUIT_NOM}",
                          f"{email}\n{nom}", settings.DEFAULT_FROM_EMAIL, [destinataire])
            except Exception:
                logger.exception("Notification de demande d'invitation non envoyée")
    messages.success(request, _("Merci ! Nous vous écrivons très vite avec votre invitation."))
    return redirect(ancre)
