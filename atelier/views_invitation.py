"""Création d'un atelier et de son compte à partir d'une invitation."""
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

from .forms import InscriptionForm
from .models import Adhesion, Atelier, Invitation


def _invalide(request):
    # Même réponse pour « inconnue », « expirée » et « déjà utilisée » : rien à deviner pour un tiers.
    return render(request, 'atelier/invitation_invalide.html', status=410)


@never_cache
def accepter_invitation(request, jeton):
    invitation = Invitation.trouver(jeton)
    if invitation is None or not invitation.est_utilisable:
        return _invalide(request)

    if request.method == 'POST':
        form = InscriptionForm(request.POST, email=invitation.email)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Verrou : deux envois simultanés du même lien ne peuvent créer qu'un seul atelier.
                    invitation = Invitation.trouver(jeton, pour_modifier=True)
                    if invitation is None or not invitation.est_utilisable:
                        return _invalide(request)
                    atelier = Atelier.objects.create(nom=form.cleaned_data['nom_atelier'].strip())
                    utilisateur = User.objects.create_user(
                        username=form.cleaned_data['identifiant'], email=invitation.email,
                        password=form.cleaned_data['mot_de_passe'])
                    Adhesion.objects.create(
                        user=utilisateur, atelier=atelier, role='PROPRIETAIRE',
                        langue=getattr(request, 'LANGUAGE_CODE', 'he'))
                    invitation.utilisee_le = timezone.now()
                    invitation.atelier = atelier
                    invitation.save(update_fields=['utilisee_le', 'atelier'])
            except IntegrityError:  # identifiant pris entre la vérification et la création
                form.add_error('identifiant', _("Cet identifiant est déjà pris."))
            else:
                login(request, utilisateur, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('dashboard')
    else:
        form = InscriptionForm(initial={'nom_atelier': invitation.nom_atelier}, email=invitation.email)

    return render(request, 'atelier/invitation.html', {'form': form, 'invitation': invitation})
