"""Ateliers (comptes clients du service) et rattachement des utilisateurs.

Chaque atelier est un « locataire » : toutes ses données portent la clé `atelier`, et une
utilisatrice ne voit que celles de son atelier. Les modèles métier héritent de `ModeleAtelier`.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Atelier(models.Model):
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('ESSAI', 'En essai'),
        ('SUSPENDU', 'Suspendu'),
    ]
    OFFRE_CHOICES = [
        ('GRATUIT', 'Gratuit (lancement)'),
    ]

    nom = models.CharField(max_length=150, verbose_name="Nom de l'atelier")
    contact_confidentialite = models.CharField(
        max_length=200, blank=True, verbose_name="Contact pour la protection des données",
        help_text="E-mail ou téléphone où une cliente peut exercer ses droits (fiche d'information).")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='ACTIF')
    offre = models.CharField(max_length=10, choices=OFFRE_CHOICES, default='GRATUIT')
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['nom']
        verbose_name = "Atelier"
        verbose_name_plural = "Ateliers"

    @property
    def est_suspendu(self):
        return self.statut == 'SUSPENDU'

    def __str__(self):
        return self.nom


class Adhesion(models.Model):
    """Rattache un identifiant à UN atelier. Pour l'instant : une propriétaire par atelier."""
    ROLE_CHOICES = [
        ('PROPRIETAIRE', 'Propriétaire'),
        ('EMPLOYE', 'Employée'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='adhesion')
    atelier = models.ForeignKey(Atelier, on_delete=models.CASCADE, related_name='adhesions')
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='PROPRIETAIRE')

    class Meta:
        verbose_name = "Adhésion"
        verbose_name_plural = "Adhésions"

    def __str__(self):
        return f"{self.user} → {self.atelier}"


class AtelierQuerySet(models.QuerySet):
    def de(self, atelier):
        """Seules les lignes de cet atelier. À utiliser pour TOUTE lecture dans une vue ou un service."""
        return self.filter(atelier=atelier)


class AtelierManager(models.Manager.from_queryset(AtelierQuerySet)):
    pass


class ModeleAtelier(models.Model):
    """Base des modèles métier : porte la clé `atelier` et refuse les liens entre ateliers différents.

    `PARENTS_ATELIER` liste les relations (robe, client…) dont l'atelier doit être le même :
    à l'enregistrement, l'atelier est repris du parent s'il est absent, et une incohérence lève une erreur.
    """
    PARENTS_ATELIER = ()

    atelier = models.ForeignKey(Atelier, on_delete=models.PROTECT, related_name='+')

    # Les formulaires ne doivent JAMAIS exposer ce champ (test_isolation le vérifie) : la vue le renseigne.
    objects = AtelierManager()

    class Meta:
        abstract = True

    def _atelier_des_parents(self):
        ids = set()
        for nom in self.PARENTS_ATELIER:
            parent = getattr(self, nom)
            if parent is not None:
                ids.add(parent.atelier_id)
        return ids

    def save(self, *args, **kwargs):
        parents = self._atelier_des_parents()
        if not self.atelier_id and len(parents) == 1:
            self.atelier_id = next(iter(parents))
        if parents - {self.atelier_id}:
            raise ValidationError("Cet élément ne peut pas être lié à un élément d'un autre atelier.")
        super().save(*args, **kwargs)
