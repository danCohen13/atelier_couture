"""Location : robes du stock et contrats."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .ateliers import ModeleAtelier
from .constantes import DEVISE_CHOICES, SYMBOLES_DEVISE


class RobeLocation(ModeleAtelier):
    """
    Représente une pièce physique en stock destinée à la location.
    """
    STATUT_PHYSIQUE_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('NETTOYAGE', 'Au pressing / Nettoyage'),
        ('REPARATION', 'En réparation / Atelier'),
        ('HORS_SERVICE', 'Hors service / Retirée'),
    ]

    reference_stock = models.CharField(
        max_length=50,
        verbose_name="Référence stock (ex: LOC-042)",
        help_text="Identifiant unique étiqueté sur la robe"
    )
    nom_modele = models.CharField(max_length=150, verbose_name="Nom du modèle")
    taille = models.CharField(max_length=20, verbose_name="Taille")
    couleur = models.CharField(max_length=50, verbose_name="Couleur")
    description = models.TextField(blank=True, verbose_name="Description")
    
    photo = models.ImageField(upload_to="robes_location/", blank=True, null=True, verbose_name="Photo")
    
    devise = models.CharField(
        max_length=3, choices=DEVISE_CHOICES, default='ILS', verbose_name="Devise",
        help_text="Devise du prix et de la caution standard (₪ par défaut)"
    )
    prix_location_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix standard"
    )
    caution_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Caution standard"
    )

    cout_revient = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Coût de revient",
        help_text="Prix d'achat ou de confection de la robe, dans la devise ci-dessus (pour mesurer sa rentabilité)"
    )

    statut_physique = models.CharField(
        max_length=30,
        choices=STATUT_PHYSIQUE_CHOICES,
        default='DISPONIBLE',
        verbose_name="État de disponibilité atelier"
    )
    etat_general = models.TextField(
        blank=True,
        verbose_name="État général / Notes d'usure"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Robe en location"
        verbose_name_plural = "Robes en location"
        ordering = ['nom_modele', 'reference_stock']
        constraints = [
            models.UniqueConstraint(fields=['atelier', 'reference_stock'], name='reference_stock_unique_par_atelier'),
        ]

    def __str__(self):
        return f"{self.reference_stock} - {self.nom_modele} (T.{self.taille})"

    @property
    def symbole_devise(self):
        return SYMBOLES_DEVISE.get(self.devise, '₪')

    def est_disponible_sur_periode(self, debut, fin, exclure_location_id=None):
        if self.statut_physique in ['HORS_SERVICE', 'REPARATION']:
            return False

        locations_actives = self.locations.exclude(statut__in=['ANNULEE'])
        if exclure_location_id:
            locations_actives = locations_actives.exclude(pk=exclure_location_id)

        for loc in locations_actives:
            fin_bloquee = (loc.date_retour_effectif or loc.date_fin_prevue) + timedelta(days=loc.delai_tampon_jours)
            if loc.date_debut <= fin and debut <= fin_bloquee:
                return False
        return True


class Location(ModeleAtelier):
    PARENTS_ATELIER = ('client', 'robe_location')
    """
    Contrat et événement de location reliant une cliente à une robe physique.
    """
    STATUT_LOCATION_CHOICES = [
        ('RESERVEE', 'Réservée'),
        ('EN_COURS', 'En cours (sortie atelier)'),
        ('TERMINEE', 'Terminée (restituée)'),
        ('EN_RETARD', 'En retard de restitution'),
        ('ANNULEE', 'Annulée'),
    ]

    CAUTION_STATUT_CHOICES = [
        ('NON_DEPOSEE', 'Non déposée'),
        ('ENREGISTREE', 'Enregistrée (Chèque / Empreinte)'),
        ('RESTITUEE', 'Restituée'),
        ('ENCAISSEE_PARTIEL', 'Retenue partielle'),
        ('ENCAISSEE_TOTAL', 'Encaissée (Perte / Dégâts)'),
    ]

    client = models.ForeignKey(
        'Client',
        on_delete=models.CASCADE,
        related_name='locations',
        verbose_name="Cliente"
    )
    robe_location = models.ForeignKey(
        RobeLocation,
        on_delete=models.PROTECT,
        related_name='locations',
        verbose_name="Robe louée"
    )

    date_debut = models.DateField(verbose_name="Date de retrait prévue")
    date_fin_prevue = models.DateField(verbose_name="Date de retour prévue")
    date_retour_effectif = models.DateField(
        null=True, blank=True, verbose_name="Date de retour effective"
    )
    delai_tampon_jours = models.PositiveIntegerField(
        default=2,
        verbose_name="Jours de battement (pressing)",
        help_text="Nombre de jours de blocage après le retour pour l'entretien"
    )

    devise = models.CharField(
        max_length=3, choices=DEVISE_CHOICES, default='ILS', verbose_name="Devise",
        help_text="Devise du prix et de la caution de ce contrat (₪ par défaut)"
    )
    prix_convenu = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix de la location")
    caution_montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant de la caution")
    caution_statut = models.CharField(
        max_length=30,
        choices=CAUTION_STATUT_CHOICES,
        default='NON_DEPOSEE',
        verbose_name="Statut de la caution"
    )

    caution_retenue = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant de caution retenu",
        help_text="Partie de la caution gardée (dégâts, perte). Elle devient alors un revenu."
    )

    statut = models.CharField(
        max_length=30,
        choices=STATUT_LOCATION_CHOICES,
        default='RESERVEE',
        verbose_name="Statut du contrat"
    )

    etat_avant = models.TextField(blank=True, verbose_name="Constat d'état au départ")
    etat_apres = models.TextField(blank=True, verbose_name="Constat d'état au retour")
    notes = models.TextField(blank=True, verbose_name="Notes / Ajustements temporaires")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contrat de location"
        verbose_name_plural = "Contrats de location"
        ordering = ['-date_debut']

    def __str__(self):
        return f"Location #{self.pk} - {self.client} ({self.robe_location.reference_stock})"

    @property
    def symbole_devise(self):
        return SYMBOLES_DEVISE.get(self.devise, '₪')

    @property
    def caution_gardee(self):
        """Part de la caution conservée par l'atelier (donc un revenu)."""
        if self.caution_statut == 'ENCAISSEE_TOTAL':
            return self.caution_montant or Decimal('0')
        if self.caution_statut == 'ENCAISSEE_PARTIEL':
            return min(self.caution_retenue or Decimal('0'), self.caution_montant or Decimal('0'))
        return Decimal('0')

    @property
    def total_paye(self):
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def reste_a_payer(self):
        return (self.prix_convenu or Decimal('0')) - self.total_paye

    def clean(self):
        super().clean()

        if self.date_debut and self.date_fin_prevue:
            if self.date_debut > self.date_fin_prevue:
                raise ValidationError({
                    'date_fin_prevue': "La date de fin ne peut pas être antérieure à la date de début."
                })

            if self.robe_location_id:
                est_libre = self.robe_location.est_disponible_sur_periode(
                    debut=self.date_debut,
                    fin=self.date_fin_prevue,
                    exclure_location_id=self.pk
                )
                if not est_libre:
                    raise ValidationError(
                        f"La robe {self.robe_location.reference_stock} n'est pas disponible sur cette période "
                        f"(ou est bloquée par le délai de pressing d'une autre réservation)."
                    )

    @property
    def est_en_retard(self):
        if self.statut == 'EN_COURS' and not self.date_retour_effectif:
            return timezone.localdate() > self.date_fin_prevue
        return False
