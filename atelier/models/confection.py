"""Confection sur mesure : robes et tâches de fabrication."""

from decimal import Decimal

from django.db import models
from django.utils import timezone

from .constantes import DEVISE_CHOICES, SYMBOLES_DEVISE


class Robe(models.Model):
    DEVISE_CHOICES = DEVISE_CHOICES

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='robes')
    nom_modele = models.CharField(max_length=200)
    date_commencement = models.DateField()
    date_livraison = models.DateField()
    
    cout_tissu = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    cout_main_doeuvre = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    prix_total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default='ILS', verbose_name="Devise")
    heures_travail = models.DecimalField(
        max_digits=6, decimal_places=1, default=0, verbose_name="Heures de travail",
        help_text="Sert à calculer le gain horaire réel de la robe (facultatif)"
    )
    croquis = models.URLField(max_length=500, blank=True, null=True)
    photo_tissus = models.URLField(max_length=500, blank=True, null=True)
    
    @property
    def symbole_devise(self):
        return SYMBOLES_DEVISE.get(self.devise, '₪')

    @property
    def total_paye(self):
        """Somme des paiements reçus (utilise le prefetch `paiements` s'il existe)."""
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def reste_a_payer(self):
        return (self.prix_total or Decimal('0')) - self.total_paye

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


class Tache(models.Model):
    robe = models.ForeignKey(Robe, on_delete=models.CASCADE, related_name='taches')
    libelle = models.CharField(max_length=250)
    est_faite = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.libelle} ({'Fait' if self.est_faite else 'À faire'})"
