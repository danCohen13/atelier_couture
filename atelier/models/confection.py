"""Confection sur mesure : robes et tâches de fabrication."""


from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .ateliers import ModeleAtelier
from .constantes import DEVISE_CHOICES
from .mixins import AvecDevise, AvecPaiements


class Robe(AvecDevise, AvecPaiements, ModeleAtelier):
    """Une COMMANDE SUR MESURE (une confection) : une robe fabriquée pour une cliente.

    Ne pas confondre avec `RobeLocation` (models/location.py), une robe du STOCK que l'on loue.
    Le nom `Robe` est historique ; dans l'interface on parle de « confection » ou de « commande ».
    """
    PARENTS_ATELIER = ('client',)
    CHAMP_PRIX = 'prix_total'
    DEVISE_CHOICES = DEVISE_CHOICES

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='robes')
    nom_modele = models.CharField(max_length=200)
    date_commencement = models.DateField()
    date_livraison = models.DateField()
    
    cout_tissu = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    cout_main_doeuvre = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    prix_total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default='ILS', verbose_name=_("Devise"))
    heures_travail = models.DecimalField(
        max_digits=6, decimal_places=1, default=0, verbose_name=_("Heures de travail"),
        help_text=_("Sert à calculer le gain horaire réel de la robe (facultatif)")
    )
    croquis = models.URLField(max_length=500, blank=True, null=True)
    photo_tissus = models.URLField(max_length=500, blank=True, null=True)
    
    @property
    def jours_restants(self):
        if self.date_livraison:
            # Date locale de l'atelier (TIME_ZONE) : le serveur tourne en UTC.
            delta = self.date_livraison - timezone.localdate()
            return delta.days
        return None

    @property
    def progression(self):
        """
        Pourcentage de tâches terminées (0 à 100).

        Calculé en Python à partir de `self.taches.all()` : avec
        `prefetch_related('taches')` aucune requête SQL n'est émise, même si la
        propriété est lue plusieurs fois par robe (liste, filtre, tri…).
        """
        taches = list(self.taches.all())
        if not taches:
            return 0
        faites = sum(1 for t in taches if t.est_faite)
        return 100 * faites // len(taches)

    def __str__(self):
        return f"{self.nom_modele} - Client : {self.client.nom}"


class Tache(ModeleAtelier):
    """Une étape de fabrication d'une commande sur mesure (toile d'essai, coupe, finitions…)."""
    PARENTS_ATELIER = ('robe',)
    robe = models.ForeignKey(Robe, on_delete=models.CASCADE, related_name='taches')
    libelle = models.CharField(max_length=250)
    est_faite = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.libelle} ({'Fait' if self.est_faite else 'À faire'})"
