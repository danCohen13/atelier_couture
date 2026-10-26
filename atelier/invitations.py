"""Liens et e-mails d'invitation."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def lien_invitation(jeton):
    return settings.SITE_URL + reverse('accepter_invitation', args=[jeton])


def envoyer_invitation(invitation, jeton, langue='he'):
    """Envoie le lien à la personne invitée. Renvoie True si l'envoi a réussi (ne lève jamais d'exception)."""
    with translation.override(langue):
        sujet = _("Votre invitation à %(produit)s") % {'produit': settings.PRODUIT_NOM}
        corps = _(
            "Bonjour,\n\nVous êtes invitée à ouvrir votre atelier sur %(produit)s.\n"
            "Créez votre compte avec ce lien personnel (valable %(jours)s jours, à usage unique) :\n\n%(lien)s\n"
        ) % {'produit': settings.PRODUIT_NOM, 'jours': invitation.DUREE_JOURS, 'lien': lien_invitation(jeton)}
    try:
        send_mail(sujet, corps, settings.DEFAULT_FROM_EMAIL, [invitation.email])
        return True
    except Exception:  # SMTP indisponible, clé Brevo erronée…
        logger.exception("Échec de l'envoi de l'invitation %s", invitation.pk)
        return False
