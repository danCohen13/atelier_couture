from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .acces import atelier_requis
from .forms import AtelierReglagesForm
from .models import Client
from .services import confidentialite as vie_privee
from .services.pdf import reponse_pdf


def _annees(request):
    try:
        annees = int(request.GET.get('annees', settings.CONSERVATION_ANNEES_INACTIVITE))
    except (TypeError, ValueError):
        annees = settings.CONSERVATION_ANNEES_INACTIVITE
    return min(max(annees, 1), 20)


@atelier_requis
def confidentialite(request):
    annees = _annees(request)
    return render(request, 'atelier/confidentialite/hub.html', {
        'annees': annees,
        'inactives': vie_privee.clientes_inactives(request.atelier, annees),
        'contact': request.atelier.contact_confidentialite,
        'form_atelier': AtelierReglagesForm(instance=request.atelier),
        'sans_information': Client.objects.de(request.atelier).filter(
            information_remise_le__isnull=True, anonymisee_le__isnull=True).count(),
    })


@atelier_requis
@require_POST
def reglages_atelier(request):
    """Nom de l'atelier et coordonnées imprimées sur la fiche d'information."""
    form = AtelierReglagesForm(request.POST, instance=request.atelier)
    if form.is_valid():
        form.save()
        messages.success(request, _("Coordonnées enregistrées."))
    else:
        messages.error(request, _("Le nom de l'atelier est obligatoire."))
    return redirect('confidentialite')


@atelier_requis
def fiche_information_pdf(request):
    contexte = {
        'atelier': request.atelier.nom,
        'contact': request.atelier.contact_confidentialite,
        'annees': settings.CONSERVATION_ANNEES_INACTIVITE,
        'date_edition': timezone.localdate(),
    }
    return reponse_pdf(request, 'atelier/pdf/fiche_information.html', contexte,
                       'fiche-information-cliente.pdf', 'confidentialite')


@atelier_requis
@require_POST
def information_remise(request, client_id):
    cliente = get_object_or_404(Client.objects.de(request.atelier), pk=client_id)
    cliente.information_remise_le = timezone.localdate()
    cliente.save(update_fields=['information_remise_le'])
    messages.success(request, _("Remise de la fiche d'information enregistrée."))
    return redirect('fiche_cliente', client_id=cliente.pk)


@atelier_requis
@require_POST
def supprimer_cliente(request, client_id):
    cliente = get_object_or_404(Client.objects.de(request.atelier), pk=client_id)
    resultat = vie_privee.supprimer_ou_anonymiser(cliente)
    if resultat == 'supprimee':
        messages.success(request, _("Dossier supprimé."))
    else:
        messages.success(
            request, _("Données personnelles effacées. Les commandes et paiements sont conservés "
                       "sans lien avec son identité (obligations comptables)."))
    return redirect('liste_clientes')
