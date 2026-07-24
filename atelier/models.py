import datetime
import random
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth.models import User

class Client(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    
    # Validation du numéro international (ex: +33612345678)
    phone_regex = RegexValidator(regex=r'^\+?[1-9]\d{8,14}$', message="Le numéro doit être au format international, ex: '+33612345678'.")
    telephone = models.CharField(validators=[phone_regex], max_length=17, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    # Ajout de la date de naissance
    date_naissance = models.DateField(blank=True, null=True)
    
    # Mensurations (DecimalField pour la précision des centimètres)
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

    # NOUVEAU : Calcul dynamique du délai restant
    @property
    def jours_restants(self):
        if self.date_livraison:
            delta = self.date_livraison - datetime.date.today()
            return delta.days
        return None

    # NOUVEAU : Calcul dynamique de la progression
    @property
    def progression(self):
        taches = self.taches.all()
        total_taches = taches.count()
        if total_taches > 0:
            faites = taches.filter(est_faite=True).count()
            return int((faites / total_taches) * 100)
        return 0

    def __str__(self):
        return f"{self.nom_modele} - Client : {self.client.nom}"

class Tache(models.Model):
    # Relation : Une tâche est liée à une robe spécifique.
    robe = models.ForeignKey(Robe, on_delete=models.CASCADE, related_name='taches')
    libelle = models.CharField(max_length=250)
    est_faite = models.BooleanField(default=False)  # Permettra de cocher l'étape

    def __str__(self):
        return f"{self.libelle} ({'Fait' if self.est_faite else 'À faire'})"

class Transaction(models.Model):
    TYPE_CHOICES = [
        ('RECETTE', '🟢 Recette (Entrée d\'argent)'),
        ('DEPENSE', '🔴 Dépense (Sortie d\'argent)'),
    ]
    
    CATEGORIE_CHOICES = [
        ('PAIEMENT_CLIENT', 'Paiement de cliente'),
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
    
    # 🔗 LIAISON OPTIONNELLE AVEC UNE ROBE
    # Si on supprime une robe de l'atelier, on ne veut SURTOUT PAS effacer l'argent dans la compta.
    # On utilise models.SET_NULL pour garder la trace financière même si la robe disparaît.
    robe = models.ForeignKey(
        'Robe', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'
    )

    class Meta:
        ordering = ['-date', '-id'] # Affiche toujours les opérations les plus récentes en premier

    def __str__(self):
        return f"{self.designation} ({self.montant} ₪)"


class CodeReinitialisation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def est_valide(self):
        # Le code expire au bout de 10 minutes
        return timezone.now() < self.created_at + datetime.timedelta(minutes=10)

    @staticmethod
    def generer_code():
        return str(random.randint(100000, 999999))        