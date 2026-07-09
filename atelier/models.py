from django.db import models

class Client(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    # Mensurations (DecimalField pour la précision des centimètres)
    tour_poitrine = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tour_taille = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tour_hanches = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    hauteur_buste = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    notes_morphologie = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom}"


class Robe(models.Model):
    # Relation : Une robe appartient à un client. Si le client est supprimé, ses robes aussi (CASCADE).
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='robes')
    nom_modele = models.CharField(max_length=200)
    date_commencement = models.DateField()
    date_livraison = models.DateField()
    
    # Finances (max_digits=8 permet de gérer des montants jusqu'à 999 999.99 €)
    cout_tissu = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    cout_main_doeuvre = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    prix_total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nom_modele} - Client : {self.client.nom}"


class Tache(models.Model):
    # Relation : Une tâche est liée à une robe spécifique.
    robe = models.ForeignKey(Robe, on_delete=models.CASCADE, related_name='taches')
    libelle = models.CharField(max_length=250)
    est_faite = models.BooleanField(default=False)  # Permettra de cocher l'étape

    def __str__(self):
        return f"{self.libelle} ({'Fait' if self.est_faite else 'À faire'})"