from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Client
from .services import confidentialite as vie_privee
from .services.pdf import reponse_pdf


def _annees(request):
    try:
        annees = int(request.GET.get('annees', settings.CONSERVATION_ANNEES_INACTIVITE))
    except (TypeError, ValueError):
        annees = settings.CONSERVATION_ANNEES_INACTIVITE
    return min(max(annees, 1), 20)


@login_required
def confidentialite(request):
    annees = _annees(request)
    return render(request, 'atelier/confidentialite/hub.html', {
        'annees': annees,
        'inactives': vie_privee.clientes_inactives(annees),
        'contact': settings.CONTACT_CONFIDENTIALITE,
        'sans_information': Client.objects.filter(
            information_remise_le__isnull=True, anonymisee_le__isnull=True).count(),
    })


@login_required
def fiche_information_pdf(request):
    contexte = {
        'atelier': settings.ATELIER_NOM,
        'contact': settings.CONTACT_CONFIDENTIALITE,
        'annees': settings.CONSERVATION_ANNEES_INACTIVITE,
        'date_edition': timezone.localdate(),
    }
    return reponse_pdf(request, 'atelier/pdf/fiche_information.html', contexte,
                       'fiche-information-cliente.pdf', 'confidentialite')


@login_required
@require_POST
def information_remise(request, client_id):
    cliente = get_object_or_404(Client, pk=client_id)
    cliente.information_remise_le = timezone.localdate()
    cliente.save(update_fields=['information_remise_le'])
    messages.success(request, "Remise de la fiche d'information enregistrée.")
    return redirect('fiche_cliente', client_id=cliente.pk)


@login_required
@require_POST
def supprimer_cliente(request, client_id):
    cliente = get_object_or_404(Client, pk=client_id)
    resultat = vie_privee.supprimer_ou_anonymiser(cliente)
    if resultat == 'supprimee':
        messages.success(request, "Dossier supprimé.")
    else:
        messages.success(
            request, "Données personnelles effacées. Les commandes et paiements sont conservés "
                     "sans lien avec son identité (obligations comptables).")
    return redirect('liste_clientes')
