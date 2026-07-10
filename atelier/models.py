from django.db import models
from django.core.validators import RegexValidator

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
    # Liste des devises disponibles
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
    
    # Nouveau champ avec le Shekel ('ILS') défini par défaut
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default='ILS', verbose_name="Devise")

    # Propriété magique pour récupérer instantanément le symbole associé
    @property
    def symbole_devise(self):
        mapping = {'ILS': '₪', 'EUR': '€', 'USD': '$'}
        return mapping.get(self.devise, '₪')

    def __str__(self):
        return f"{self.nom_modele} - Client : {self.client.nom}"

class Tache(models.Model):
    # Relation : Une tâche est liée à une robe spécifique.
    robe = models.ForeignKey(Robe, on_delete=models.CASCADE, related_name='taches')
    libelle = models.CharField(max_length=250)
    est_faite = models.BooleanField(default=False)  # Permettra de cocher l'étape

    def __str__(self):
        return f"{self.libelle} ({'Fait' if self.est_faite else 'À faire'})"