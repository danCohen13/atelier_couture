import datetime
import random
from datetime import timedelta
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Client(models.Model):
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
    notes_morphologie = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom}"


class Robe(models.Model):
    DEVISE_CHOICES = [
        ('ILS', '₪ (Shekel)'),
        ('EUR', '€ (Euro)'),
        ('USD', '$ (Dollar)'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='robes')
    nom_modele = models.CharField(max_length=200)
    date_commencement = models.DateField()
    date_livraison = models.DateField()
    
    cout_tissu = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    cout_main_doeuvre = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    prix_total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default='ILS', verbose_name="Devise")
    croquis = models.URLField(max_length=500, blank=True, null=True)
    photo_tissus = models.URLField(max_length=500, blank=True, null=True)
    
    @property
    def symbole_devise(self):
        mapping = {'ILS': '₪', 'EUR': '€', 'USD': '$'}
        return mapping.get(self.devise, '₪')

    @property
    def jours_restants(self):
        if self.date_livraison:
            delta = self.date_livraison - datetime.date.today()
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


class Transaction(models.Model):
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
    location = models.ForeignKey(
    'Location',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='transactions',
    verbose_name="Location associée"
    )

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.designation} ({self.montant} ₪)"


class CodeReinitialisation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def est_valide(self):
        return timezone.now() < self.created_at + datetime.timedelta(minutes=10)

    @staticmethod
    def generer_code():
        return str(random.randint(100000, 999999))


class RobeLocation(models.Model):
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
        unique=True,
        verbose_name="Référence stock (ex: LOC-042)",
        help_text="Identifiant unique étiqueté sur la robe"
    )
    nom_modele = models.CharField(max_length=150, verbose_name="Nom du modèle")
    taille = models.CharField(max_length=20, verbose_name="Taille")
    couleur = models.CharField(max_length=50, verbose_name="Couleur")
    description = models.TextField(blank=True, verbose_name="Description")
    
    photo = models.ImageField(upload_to="robes_location/", blank=True, null=True, verbose_name="Photo")
    
    prix_location_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix standard (€)"
    )
    caution_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Caution standard (€)"
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

    def __str__(self):
        return f"{self.reference_stock} - {self.nom_modele} (T.{self.taille})"

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


class Location(models.Model):
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
        Client,
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

    prix_convenu = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix de la location (€)")
    caution_montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant de la caution (€)")
    caution_statut = models.CharField(
        max_length=30,
        choices=CAUTION_STATUT_CHOICES,
        default='NON_DEPOSEE',
        verbose_name="Statut de la caution"
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
            return timezone.now().date() > self.date_fin_prevue
        return False