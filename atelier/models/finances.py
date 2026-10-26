"""Finances : opérations manuelles, paiements, dépenses récurrentes, réglages."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .ateliers import Atelier, ModeleAtelier
from .constantes import SYMBOLES_DEVISE


class Transaction(ModeleAtelier):
    PARENTS_ATELIER = ('robe', 'location', 'recurrente')

    TYPE_CHOICES = [
        ('RECETTE', '🟢 Recette (Entrée d\'argent)'),
        ('DEPENSE', '🔴 Dépense (Sortie d\'argent)'),
    ]
    
    CATEGORIE_CHOICES = [
        ('PAIEMENT_CLIENT', 'Paiement de cliente'),
        ('LOCATION_ROBE', 'Location de robe'),
        ('TISSU', 'Achat de tissu'),
        ('FOURNITURES', 'Fournitures (Fils, fermetures, boutons...)'),
        ('MATERIEL', 'Matériel & Machines (Entretien, achat...)'),
        ('AUTRE', 'Autre frais / Divers'),
    ]

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES)
    designation = models.CharField(max_length=255, help_text="Ex: Acompte robe Salome, Achat fils noirs...")
    date = models.DateField(default=timezone.now)
    
    robe = models.ForeignKey(
        'Robe',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'
    )
    location = models.ForeignKey(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name="Location associée"
    )
    justificatif = models.URLField(
        max_length=500, blank=True, default='', verbose_name="Photo du justificatif",
        help_text="Photo du ticket ou de la facture (facultatif)"
    )
    recurrente = models.ForeignKey(
        'DepenseRecurrente', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions', verbose_name="Dépense récurrente d'origine"
    )

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.designation} ({self.montant} ₪)"


class Paiement(ModeleAtelier):
    PARENTS_ATELIER = ('robe', 'location')

    """Somme reçue d'une cliente (acompte ou solde) pour une robe sur mesure ou une location."""
    MODE_CHOICES = [
        ('ESPECES', 'Espèces'),
        ('VIREMENT', 'Virement'),
        ('CARTE', 'Carte bancaire'),
        ('CHEQUE', 'Chèque'),
        ('AUTRE', 'Autre'),
    ]

    robe = models.ForeignKey('Robe', on_delete=models.CASCADE, null=True, blank=True, related_name='paiements')
    location = models.ForeignKey('Location', on_delete=models.CASCADE, null=True, blank=True, related_name='paiements')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='ESPECES', verbose_name="Mode de paiement")
    note = models.CharField(max_length=200, blank=True, verbose_name="Note")

    class Meta:
        ordering = ['date', 'id']

    def clean(self):
        super().clean()
        if bool(self.robe_id) == bool(self.location_id):
            raise ValidationError("Un paiement concerne soit une robe sur mesure, soit une location.")
        if self.montant is not None and self.montant <= 0:
            raise ValidationError({'montant': "Le montant doit être positif."})

    @property
    def cible(self):
        return self.robe or self.location

    @property
    def devise(self):
        return self.cible.devise if self.cible else 'ILS'

    @property
    def symbole_devise(self):
        return SYMBOLES_DEVISE.get(self.devise, '₪')

    def __str__(self):
        return f"Paiement {self.montant} {self.symbole_devise} ({self.date})"


class DepenseRecurrente(ModeleAtelier):
    """Charge qui revient chaque mois (loyer, abonnement…) : l'écriture est créée automatiquement."""
    designation = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    categorie = models.CharField(
        max_length=20, choices=[c for c in Transaction.CATEGORIE_CHOICES if c[0] not in ('PAIEMENT_CLIENT', 'LOCATION_ROBE')],
        default='AUTRE'
    )
    jour_du_mois = models.PositiveSmallIntegerField(default=1, verbose_name="Jour du mois (1 à 28)")
    date_debut = models.DateField(default=timezone.localdate, verbose_name="À partir du")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['designation']
        verbose_name = "Dépense récurrente"
        verbose_name_plural = "Dépenses récurrentes"

    def clean(self):
        super().clean()
        if self.jour_du_mois is not None and not 1 <= self.jour_du_mois <= 28:
            raise ValidationError({'jour_du_mois': "Choisis un jour entre 1 et 28."})
        if self.montant is not None and self.montant <= 0:
            raise ValidationError({'montant': "Le montant doit être positif."})

    def __str__(self):
        return f"{self.designation} ({self.montant} ₪/mois)"


class ParametresFinance(models.Model):
    """Réglages de la comptabilité d'un atelier : taux de change vers le shekel et objectif mensuel."""
    atelier = models.OneToOneField(Atelier, on_delete=models.PROTECT, related_name='parametres_finance')
    taux_eur = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True, verbose_name="1 € vaut … ₪")
    taux_usd = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True, verbose_name="1 $ vaut … ₪")
    objectif_mensuel = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Objectif de chiffre d'affaires mensuel (₪)")

    class Meta:
        verbose_name = "Paramètres de finance"
        verbose_name_plural = "Paramètres de finance"

    @classmethod
    def charger(cls, atelier):
        """Réglages de cet atelier (créés à la première lecture)."""
        obj, _ = cls.objects.get_or_create(atelier=atelier)
        return obj

    def taux(self, devise):
        """Valeur d'une unité de `devise` en shekels, ou None si le taux n'est pas renseigné."""
        if devise == 'ILS':
            return Decimal('1')
        return {'EUR': self.taux_eur, 'USD': self.taux_usd}.get(devise) or None

    def __str__(self):
        return "Paramètres de finance"
