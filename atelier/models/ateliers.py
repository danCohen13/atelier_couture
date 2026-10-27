"""Ateliers (comptes clients du service) et rattachement des utilisateurs.

Chaque atelier est un « locataire » : toutes ses données portent la clé `atelier`, et une
utilisatrice ne voit que celles de son atelier. Les modèles métier héritent de `ModeleAtelier`.
"""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Atelier(models.Model):
    STATUT_CHOICES = [
        ('ACTIF', _('Actif')),
        ('ESSAI', _('En essai')),
        ('SUSPENDU', _('Suspendu')),
    ]
    OFFRE_CHOICES = [
        ('GRATUIT', _('Gratuit (lancement)')),
    ]

    nom = models.CharField(max_length=150, verbose_name=_("Nom de l'atelier"))
    contact_confidentialite = models.CharField(
        max_length=200, blank=True, verbose_name=_("Contact pour la protection des données"),
        help_text=_("E-mail ou téléphone où une cliente peut exercer ses droits (fiche d'information)."))
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


class Invitation(models.Model):
    """Invitation à ouvrir un atelier. L'inscription est sur invitation uniquement.

    Le lien contient un jeton aléatoire ; seule son empreinte (SHA-256) est conservée en base : une fuite
    de la base ne permet donc pas d'utiliser les invitations en attente. Un lien ne sert qu'une fois.
    """
    DUREE_JOURS = 7

    email = models.EmailField(verbose_name=_("Adresse e-mail de la personne invitée"))
    nom_atelier = models.CharField(max_length=150, blank=True, verbose_name=_("Nom d'atelier proposé"))
    jeton_hash = models.CharField(max_length=64, unique=True, editable=False)
    cree_le = models.DateTimeField(default=timezone.now, editable=False)
    expire_le = models.DateTimeField(editable=False)
    utilisee_le = models.DateTimeField(null=True, blank=True, editable=False)
    atelier = models.ForeignKey(Atelier, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='+', editable=False)

    class Meta:
        ordering = ['-cree_le']
        verbose_name = "Invitation"
        verbose_name_plural = "Invitations"

    @staticmethod
    def empreinte(jeton):
        return hashlib.sha256(jeton.encode('utf-8')).hexdigest()

    @classmethod
    def creer(cls, email, nom_atelier='', jours=DUREE_JOURS):
        """Crée l'invitation et renvoie `(invitation, jeton)` : le jeton n'est connu qu'à cet instant."""
        email = email.strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("Un compte existe déjà avec cette adresse e-mail."))
        jeton = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            email=email, nom_atelier=nom_atelier.strip(), jeton_hash=cls.empreinte(jeton),
            expire_le=timezone.now() + timedelta(days=jours))
        return invitation, jeton

    @classmethod
    def trouver(cls, jeton, pour_modifier=False):
        """L'invitation correspondant au jeton, ou None. Ne dit pas si elle est utilisable."""
        requete = cls.objects.select_for_update() if pour_modifier else cls.objects
        return requete.filter(jeton_hash=cls.empreinte(jeton or '')).first()

    @property
    def est_utilisable(self):
        return self.utilisee_le is None and self.expire_le > timezone.now()

    def __str__(self):
        return f"{self.email} ({'utilisée' if self.utilisee_le else 'en attente'})"


class DemandeInvitation(models.Model):
    """Demande faite depuis la page d'accueil. Elle ne crée aucun compte : l'exploitante invite ensuite."""
    email = models.EmailField(verbose_name=_("Adresse e-mail"))
    nom_atelier = models.CharField(max_length=150, blank=True, verbose_name=_("Nom de l'atelier"))
    cree_le = models.DateTimeField(default=timezone.now, editable=False)
    traitee = models.BooleanField(default=False, verbose_name=_("Invitation envoyée"))

    class Meta:
        ordering = ['traitee', '-cree_le']
        verbose_name = "Demande d'invitation"
        verbose_name_plural = "Demandes d'invitation"

    def __str__(self):
        return f"{self.email} — {self.nom_atelier}" if self.nom_atelier else self.email


class Adhesion(models.Model):
    """Rattache un identifiant à UN atelier. Pour l'instant : une propriétaire par atelier."""
    ROLE_CHOICES = [
        ('PROPRIETAIRE', _('Propriétaire')),
        ('EMPLOYE', _('Employée')),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='adhesion')
    atelier = models.ForeignKey(Atelier, on_delete=models.CASCADE, related_name='adhesions')
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='PROPRIETAIRE')
    langue = models.CharField(
        max_length=5, choices=[('he', 'עברית'), ('fr', 'Français')], default='he',
        help_text=_("Langue de l'interface de cette utilisatrice."))

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
            raise ValidationError(_("Cet élément ne peut pas être lié à un élément d'un autre atelier."))
        super().save(*args, **kwargs)
