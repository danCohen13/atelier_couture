"""Sécurité : codes de réinitialisation et registre des incidents."""

import datetime
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class CodeReinitialisation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    tentatives = models.PositiveSmallIntegerField(default=0)  # essais ratés sur ce code

    def est_valide(self):
        return timezone.now() < self.created_at + datetime.timedelta(minutes=10)

    @staticmethod
    def generer_code():
        # `secrets` (et non `random`) : le code protège l'accès au compte.
        return str(100000 + secrets.randbelow(900000))


class IncidentSecurite(models.Model):
    """Registre des incidents de sécurité (obligation de documenter, règlement de sécurité 2017)."""
    date_constat = models.DateField(default=timezone.localdate, verbose_name="Date du constat")
    description = models.TextField(help_text="Ce qui s'est passé (perte d'un téléphone, accès suspect…)")
    donnees_concernees = models.CharField(max_length=255, blank=True, verbose_name="Données concernées")
    mesures_prises = models.TextField(blank=True, verbose_name="Mesures prises")
    grave = models.BooleanField(
        default=False, verbose_name="Incident grave",
        help_text="Accès non autorisé ou atteinte à l'intégrité d'une partie importante des données : "
                  "à signaler immédiatement à l'Autorité israélienne de protection de la vie privée.")
    signale_autorite_le = models.DateField(blank=True, null=True, verbose_name="Signalé à l'Autorité le")

    class Meta:
        ordering = ['-date_constat', '-id']
        verbose_name = "Incident de sécurité"
        verbose_name_plural = "Incidents de sécurité"

    def __str__(self):
        return f"{self.date_constat} — {self.description[:50]}"
