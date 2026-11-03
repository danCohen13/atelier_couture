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


def tableau_du_jour(atelier, aujourdhui=None):
    """Renvoie {'sections': [Section…], 'compteurs': {…}, 'vide': bool}."""
    aujourdhui = aujourdhui or timezone.localdate()
    limite = aujourdhui + datetime.timedelta(days=JOURS_A_VENIR)

    robes = list(Robe.objects.de(atelier).select_related('client').prefetch_related('taches', 'paiements'))
    contrats = list(Location.objects.de(atelier).exclude(statut='ANNULEE')
                    .select_related('client', 'robe_location').prefetch_related('paiements'))
    actives = _robes_a_livrer(robes)

    # --- 1. À traiter maintenant -------------------------------------------------
    urgent = Section('urgent', _("À traiter maintenant"))
    for robe in sorted((r for r in actives if r.date_livraison < aujourdhui), key=lambda r: r.date_livraison):
        e = _element_robe(robe, aujourdhui)
        e.genre = 'livraison_en_retard'
        urgent.elements.append(e)
    for loc in sorted((c for c in contrats if c.statut in ('EN_COURS', 'EN_RETARD') and not c.date_retour_effectif
                       and c.date_fin_prevue < aujourdhui), key=lambda c: c.date_fin_prevue):
        urgent.elements.append(_element_location(loc, 'retour_en_retard', loc.date_fin_prevue, aujourdhui))
    for loc in sorted((c for c in contrats if c.statut == 'RESERVEE' and c.date_debut < aujourdhui),
                      key=lambda c: c.date_debut):
        urgent.elements.append(_element_location(
            loc, 'retrait_manque', loc.date_debut, aujourdhui, _("Retrait prévu, robe pas encore sortie")))
    creances = compta.creances(atelier, aujourdhui, robes, contrats)
    for c in (c for c in creances if c['en_retard']):
        lien = reverse('paiements_robe' if c['type'] == 'robe' else 'paiements_location', args=[c['objet'].pk])
        urgent.elements.append(Element(
            'paiement_en_retard', c['libelle'], str(c['client']), c['client'].telephone or '', c['echeance'],
            _jours(c['echeance'], aujourdhui), f"{c['reste']} {c['symbole']}", lien))
    for c in compta.cautions_a_suivre(atelier, contrats):
        if c['a_restituer']:
            loc = c['location']
            urgent.elements.append(_element_location(
                loc, 'caution_a_restituer', loc.date_retour_effectif or loc.date_fin_prevue, aujourdhui,
                f"{loc.caution_montant} {loc.symbole_devise}"))

    # --- 2. Aujourd'hui -----------------------------------------------------------
    jour = Section('aujourdhui', _("Aujourd'hui"))
    for robe in (r for r in actives if r.date_livraison == aujourdhui):
        jour.elements.append(_element_robe(robe, aujourdhui))
    for loc in (c for c in contrats if c.statut == 'RESERVEE' and c.date_debut == aujourdhui):
        jour.elements.append(_element_location(loc, 'retrait', loc.date_debut, aujourdhui))
    for loc in (c for c in contrats if c.statut in ('EN_COURS', 'EN_RETARD') and not c.date_retour_effectif
                and c.date_fin_prevue == aujourdhui):
        jour.elements.append(_element_location(loc, 'retour', loc.date_fin_prevue, aujourdhui))

    # --- 3. Les 7 prochains jours -------------------------------------------------
    semaine = Section('semaine', _("Les 7 prochains jours"))
    for robe in sorted((r for r in actives if aujourdhui < r.date_livraison <= limite), key=lambda r: r.date_livraison):
        semaine.elements.append(_element_robe(robe, aujourdhui))
    for loc in (c for c in contrats if c.statut == 'RESERVEE' and aujourdhui < c.date_debut <= limite):
        semaine.elements.append(_element_location(loc, 'retrait', loc.date_debut, aujourdhui))
    for loc in (c for c in contrats if c.statut in ('EN_COURS', 'EN_RETARD') and not c.date_retour_effectif
                and aujourdhui < c.date_fin_prevue <= limite):
        semaine.elements.append(_element_location(loc, 'retour', loc.date_fin_prevue, aujourdhui))
    semaine.elements.sort(key=lambda e: (e.date, e.genre))

    sections = [s for s in (urgent, jour, semaine) if s.elements]
    return {
        'sections': sections,
        'compteurs': {s.cle: len(s.elements) for s in (urgent, jour, semaine)},
        'vide': not sections,
    }
