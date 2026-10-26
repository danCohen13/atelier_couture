"""Clientes de l'atelier."""


from django.core.validators import RegexValidator
from django.db import models

from .ateliers import ModeleAtelier


class Client(ModeleAtelier):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    
    phone_regex = RegexValidator(
        regex=r'^\+?[1-9]\d{8,14}$', 
        message="Le numéro doit être au format international, ex: '+33612345678'."
    )
    telephone = models.CharField(validators=[phone_regex], max_length=17, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    
    tour_poitrine = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tour_taille = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tour_hanches = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    hauteur_buste = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    notes_morphologie = models.TextField(
        blank=True, null=True,
        help_text="Morphologie uniquement (épaules, posture…). N'écris aucune information médicale."
    )

    # Protection de la vie privée : preuve que la cliente a reçu la fiche d'information,
    # date de création (pour repérer les dossiers inactifs) et trace d'une anonymisation.
    information_remise_le = models.DateField(
        blank=True, null=True, verbose_name="Fiche d'information remise le")
    cree_le = models.DateTimeField(auto_now_add=True, null=True)
    anonymisee_le = models.DateTimeField(blank=True, null=True)

    @property
    def est_anonymisee(self):
        return self.anonymisee_le is not None

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom}"
