"""Langue de l'interface : hébreu par défaut, français au choix.

Ordre de décision : cookie (choix fait sur cet appareil) → langue enregistrée sur le compte → hébreu.
On n'utilise PAS l'en-tête Accept-Language du navigateur : une cliente dont le navigateur est en français
ou en anglais doit quand même arriver sur la version hébraïque.
"""
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

LANGUES = {code for code, _ in settings.LANGUAGES}
DUREE_COOKIE = 365 * 24 * 3600


def _langue_valide(code):
    return code if code in LANGUES else None


class LangueMiddleware:
    """À placer après AuthenticationMiddleware.

    Sans cookie, l'hébreu s'applique ; pour une utilisatrice connectée, `@atelier_requis` applique la
    langue du compte (il a déjà lu l'adhésion : aucune requête de plus) via `adopter_langue_du_compte`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        langue = _langue_valide(request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)) or settings.LANGUAGE_CODE
        translation.activate(langue)
        request.LANGUAGE_CODE = langue
        request.langue_du_compte = None
        reponse = self.get_response(request)
        if request.langue_du_compte:
            reponse.set_cookie(settings.LANGUAGE_COOKIE_NAME, request.langue_du_compte, max_age=DUREE_COOKIE, samesite='Lax')
        reponse.headers.setdefault('Content-Language', translation.get_language() or langue)
        return reponse


def adopter_langue_du_compte(request, adhesion):
    """Sans cookie (nouvel appareil, après connexion), reprend la langue enregistrée sur le compte."""
    if settings.LANGUAGE_COOKIE_NAME in request.COOKIES:
        return
    langue = _langue_valide(adhesion.langue)
    if langue:
        translation.activate(langue)
        request.LANGUAGE_CODE = langue
        request.langue_du_compte = langue


@require_POST
def changer_langue(request):
    """Change la langue (POST `langue`, `next`). Accessible aussi sur la page de connexion."""
    langue = _langue_valide(request.POST.get('langue'))
    suite = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(suite, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        suite = resolve_url('dashboard')
    reponse = HttpResponseRedirect(suite)
    if langue:
        reponse.set_cookie(settings.LANGUAGE_COOKIE_NAME, langue, max_age=DUREE_COOKIE, samesite='Lax')
        if request.user.is_authenticated and hasattr(request.user, 'adhesion'):
            request.user.adhesion.langue = langue
            request.user.adhesion.save(update_fields=['langue'])
    return reponse
