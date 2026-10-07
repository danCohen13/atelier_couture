"""Génération de PDF à partir de templates HTML (xhtml2pdf)."""
import os
from io import BytesIO

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa


def link_callback(uri, rel):
    """Résout les chemins {% static %} pour que xhtml2pdf trouve le fichier CSS sur le disque."""
    if uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    else:
        path = uri

    if not os.path.isfile(path):
        result = finders.find(uri.replace(settings.STATIC_URL, ""))
        if result:
            path = result[0] if isinstance(result, (list, tuple)) else result
        else:
            return None
    return path


def render_to_pdf(template_src, context_dict=None):
    """Génère la réponse PDF à partir d'un template HTML et de son contexte (None si échec)."""
    html = get_template(template_src).render(context_dict or {})
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return None
