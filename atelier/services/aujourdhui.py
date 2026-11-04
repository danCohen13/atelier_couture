"""Écran « Aujourd'hui » : ce qui demande l'attention de l'atelier, du plus urgent au plus lointain.

Aucune donnée nouvelle : tout vient des commandes, des locations et des paiements déjà enregistrés,
avec les mêmes règles que les pages Finances et Locations (un chiffre ne peut pas différer d'une page à l'autre).
Seules les lignes de l'atelier demandé sont lues.
"""
import datetime
from dataclasses import dataclass, field

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..models import Location, Robe
from . import comptabilite as compta

JOURS_A_VENIR = 7


@dataclass
class Element:
    """Une ligne de la liste : quoi, pour qui, pour quand, et où cliquer."""
    genre: str          # code technique (livraison, retour_en_retard…), sert aux icônes et aux tests
    titre: str
    cliente: str = ''
    telephone: str = ''
    date: datetime.date | None = None
    ecart: int = 0      # jours par rapport à aujourd'hui (négatif = en retard)
    detail: str = ''
    lien: str = ''

    @property
    def ecart_absolu(self):
        return abs(self.ecart)


@dataclass
class Section:
    """Un groupe de lignes de l'écran « Aujourd'hui » (retards, aujourd'hui, semaine)."""
    cle: str
    titre: str
    elements: list = field(default_factory=list)


def _jours(date, aujourdhui):
    return (date - aujourdhui).days


def _robes_a_livrer(robes):
    """Robes non terminées (même règle que le tableau de bord : progression < 100 %)."""
    return [r for r in robes if r.progression < 100]


def _element_robe(robe, aujourdhui):
    reste_taches = [t for t in robe.taches.all() if not t.est_faite]
    detail = _("%(n)s étape(s) restante(s)") % {'n': len(reste_taches)} if reste_taches else ''
    return Element(
        'livraison', robe.nom_modele, str(robe.client), robe.client.telephone or '',
        robe.date_livraison, _jours(robe.date_livraison, aujourdhui), detail,
        reverse('fiche_cliente', args=[robe.client_id]))


def _element_location(loc, genre, date, aujourdhui, detail=''):
    robe = loc.robe_location
    return Element(
        genre, f"{robe.nom_modele} ({robe.reference_stock})", str(loc.client), loc.client.telephone or '',
        date, _jours(date, aujourdhui), detail,
        reverse('retour_location', args=[loc.pk]) if genre.startswith('retour') else reverse('tableau_bord_locations'))


def _est_sortie(contrat):
    """Robe sortie de l'atelier et pas encore rentrée."""
    return contrat.statut in ('EN_COURS', 'EN_RETARD') and not contrat.date_retour_effectif


def _livraisons(robes, aujourdhui, debut, fin=None):
    """Livraisons dont la date est entre `debut` et `fin` (inclus ; `fin=None` : jusqu'à `debut` seulement)."""
    fin = fin or debut
    return [_element_robe(r, aujourdhui) for r in sorted(robes, key=lambda r: r.date_livraison)
            if debut <= r.date_livraison <= fin]


def _retraits(contrats, aujourdhui, debut, fin=None):
    fin = fin or debut
    return [_element_location(c, 'retrait', c.date_debut, aujourdhui) for c in contrats
            if c.statut == 'RESERVEE' and debut <= c.date_debut <= fin]


def _retours(contrats, aujourdhui, debut, fin=None):
    fin = fin or debut
    return [_element_location(c, 'retour', c.date_fin_prevue, aujourdhui) for c in contrats
            if _est_sortie(c) and debut <= c.date_fin_prevue <= fin]


def _section_urgent(atelier, robes, contrats, aujourdhui):
    """Tout ce qui est déjà en retard, du plus ancien au plus récent dans chaque catégorie."""
    elements = []
    for e in _livraisons(robes, aujourdhui, datetime.date.min, aujourdhui - datetime.timedelta(days=1)):
        e.genre = 'livraison_en_retard'
        elements.append(e)
    for c in sorted((c for c in contrats if _est_sortie(c) and c.date_fin_prevue < aujourdhui),
                    key=lambda c: c.date_fin_prevue):
        elements.append(_element_location(c, 'retour_en_retard', c.date_fin_prevue, aujourdhui))
    for c in sorted((c for c in contrats if c.statut == 'RESERVEE' and c.date_debut < aujourdhui),
                    key=lambda c: c.date_debut):
        elements.append(_element_location(
            c, 'retrait_manque', c.date_debut, aujourdhui, _("Retrait prévu, robe pas encore sortie")))
    elements += _paiements_en_retard(atelier, robes, contrats, aujourdhui)
    elements += _cautions_a_restituer(atelier, contrats, aujourdhui)
    return Section('urgent', _("À traiter maintenant"), elements)


def _paiements_en_retard(atelier, robes, contrats, aujourdhui):
    elements = []
    for c in compta.creances(atelier, aujourdhui, robes, contrats):
        if not c['en_retard']:
            continue
        lien = reverse('paiements_robe' if c['type'] == 'robe' else 'paiements_location', args=[c['objet'].pk])
        elements.append(Element(
            'paiement_en_retard', c['libelle'], str(c['client']), c['client'].telephone or '', c['echeance'],
            _jours(c['echeance'], aujourdhui), f"{c['reste']} {c['symbole']}", lien))
    return elements


def _cautions_a_restituer(atelier, contrats, aujourdhui):
    elements = []
    for c in compta.cautions_a_suivre(atelier, contrats):
        if c['a_restituer']:
            loc = c['location']
            elements.append(_element_location(
                loc, 'caution_a_restituer', loc.date_retour_effectif or loc.date_fin_prevue, aujourdhui,
                f"{loc.caution_montant} {loc.symbole_devise}"))
    return elements


def _section_aujourdhui(robes, contrats, aujourdhui):
    elements = (_livraisons(robes, aujourdhui, aujourdhui) + _retraits(contrats, aujourdhui, aujourdhui)
                + _retours(contrats, aujourdhui, aujourdhui))
    return Section('aujourdhui', _("Aujourd'hui"), elements)


def _section_semaine(robes, contrats, aujourdhui):
    demain = aujourdhui + datetime.timedelta(days=1)
    limite = aujourdhui + datetime.timedelta(days=JOURS_A_VENIR)
    elements = (_livraisons(robes, aujourdhui, demain, limite) + _retraits(contrats, aujourdhui, demain, limite)
                + _retours(contrats, aujourdhui, demain, limite))
    elements.sort(key=lambda e: (e.date, e.genre))
    return Section('semaine', _("Les 7 prochains jours"), elements)


def tableau_du_jour(atelier, aujourdhui=None):
    """Renvoie {'sections': [Section…], 'compteurs': {…}, 'vide': bool} pour l'atelier donné.

    Les données sont chargées UNE fois, puis réparties dans trois sections : retards, aujourd'hui, semaine.
    """
    aujourdhui = aujourdhui or timezone.localdate()
    robes = list(Robe.objects.de(atelier).select_related('client').prefetch_related('taches', 'paiements'))
    contrats = list(Location.objects.de(atelier).exclude(statut='ANNULEE')
                    .select_related('client', 'robe_location').prefetch_related('paiements'))
    actives = _robes_a_livrer(robes)

    toutes = (_section_urgent(atelier, actives, contrats, aujourdhui),
              _section_aujourdhui(actives, contrats, aujourdhui),
              _section_semaine(actives, contrats, aujourdhui))
    sections = [s for s in toutes if s.elements]
    return {
        'sections': sections,
        'compteurs': {s.cle: len(s.elements) for s in toutes},
        'vide': not sections,
    }
