"""
Réinitialisation du mot de passe par code à 6 chiffres envoyé par e-mail.

Garde-fous :
  - la réponse est identique que l'adresse existe ou non (pas d'énumération de comptes) ;
  - un nouveau code ne peut pas être demandé plus d'une fois par minute (pas de
    « bombardement » de la boîte mail) ;
  - un code est détruit après `MAX_TENTATIVES` essais ratés (1 chance sur 200 000
    de deviner au lieu de pouvoir tout essayer pendant 10 minutes) ;
  - le nouveau mot de passe passe par les validateurs de Django.
"""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import CodeReinitialisation

logger = logging.getLogger(__name__)

MAX_TENTATIVES = 5
DELAI_ENTRE_DEUX_CODES = timedelta(minutes=1)

# Identifiant de session utilisé quand l'adresse saisie ne correspond à aucun
# compte : le parcours continue (et échoue à la vérification) comme pour un vrai compte.
UTILISATEUR_FICTIF = 0


def _trouver_utilisateur(email):
    return User.objects.filter(email__iexact=email, is_active=True).order_by('id').first()


def _envoyer_code(user, email):
    """Crée un code et l'envoie, sauf si un code vient d'être envoyé. Ne lève jamais d'exception."""
    recent = CodeReinitialisation.objects.filter(
        user=user, created_at__gt=timezone.now() - DELAI_ENTRE_DEUX_CODES
    ).exists()
    if recent:
        return

    CodeReinitialisation.objects.filter(user=user).delete()
    code = CodeReinitialisation.generer_code()
    CodeReinitialisation.objects.create(user=user, code=code)
    try:
        send_mail(
            subject=_('Votre code de réinitialisation - %(produit)s') % {'produit': settings.PRODUIT_NOM},
            message=_('Bonjour,\n\nVoici votre code de vérification à 6 chiffres : %(code)s\n\nCe code est valable pendant 10 minutes.') % {'code': code},
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
    except Exception:  # SMTP indisponible, identifiants Brevo erronés, etc.
        logger.exception("Échec de l'envoi du code de réinitialisation (utilisateur %s)", user.pk)


def demander_code_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = _trouver_utilisateur(email) if email else None

        if user:
            _envoyer_code(user, email)
            request.session['reset_user_id'] = user.id
        else:
            request.session['reset_user_id'] = UTILISATEUR_FICTIF

        request.session.pop('code_verifie', None)
        messages.info(request, _("Si un compte correspond à cette adresse, un code vient d'être envoyé."))
        return redirect('verifier_code_reset')

    return render(request, 'atelier/registration/demander_code.html')


def verifier_code_reset(request):
    user_id = request.session.get('reset_user_id')
    if user_id is None:
        return redirect('demander_code_reset')

    if request.method == 'POST':
        code_saisi = request.POST.get('code', '').strip()
        code_obj = CodeReinitialisation.objects.filter(user_id=user_id).order_by('created_at').last()

        if code_obj and code_obj.est_valide() and code_obj.tentatives < MAX_TENTATIVES:
            if secrets.compare_digest(code_obj.code, code_saisi):
                request.session['code_verifie'] = True
                code_obj.delete()
                return redirect('nouveau_mot_de_passe')

            code_obj.tentatives += 1
            if code_obj.tentatives >= MAX_TENTATIVES:
                code_obj.delete()
            else:
                code_obj.save(update_fields=['tentatives'])

        messages.error(
            request,
            _("Code invalide ou expiré (durée de validité : 10 min). "
              "Après %(n)s erreurs, il faut redemander un code.") % {'n': MAX_TENTATIVES},
        )

    return render(request, 'atelier/registration/verifier_code.html')


def nouveau_mot_de_passe(request):
    user_id = request.session.get('reset_user_id')
    code_verifie = request.session.get('code_verifie')

    if not user_id or not code_verifie:
        return redirect('demander_code_reset')

    user = User.objects.filter(id=user_id, is_active=True).first()
    if user is None:
        return redirect('demander_code_reset')

    if request.method == 'POST':
        mdp1 = request.POST.get('password')
        mdp2 = request.POST.get('password_confirm')

        if not mdp1 or mdp1 != mdp2:
            messages.error(request, _("Les mots de passe ne correspondent pas."))
        else:
            try:
                validate_password(mdp1, user)
            except ValidationError as erreurs:
                for erreur in erreurs.messages:
                    messages.error(request, erreur)
            else:
                user.set_password(mdp1)
                user.save()

                request.session.pop('reset_user_id', None)
                request.session.pop('code_verifie', None)

                messages.success(request, _("Votre mot de passe a été modifié avec succès !"))
                return redirect('login')

    return render(request, 'atelier/registration/nouveau_mot_de_passe.html')
