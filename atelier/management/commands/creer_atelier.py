"""Crée un atelier et son compte propriétaire (en attendant les invitations)."""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from atelier.models import Adhesion, Atelier


class Command(BaseCommand):
    help = "Crée un atelier avec un compte propriétaire : creer_atelier 'Nom' identifiant motdepasse [e-mail]"

    def add_arguments(self, parser):
        parser.add_argument('nom')
        parser.add_argument('identifiant')
        parser.add_argument('motdepasse')
        parser.add_argument('email', nargs='?', default='')

    def handle(self, *args, nom, identifiant, motdepasse, email, **options):
        if User.objects.filter(username=identifiant).exists():
            raise CommandError(f"L'identifiant « {identifiant} » existe déjà.")
        atelier = Atelier.objects.create(nom=nom)
        user = User.objects.create_user(username=identifiant, password=motdepasse, email=email)
        Adhesion.objects.create(user=user, atelier=atelier, role='PROPRIETAIRE')
        self.stdout.write(self.style.SUCCESS(f"Atelier « {atelier} » créé, propriétaire : {identifiant}."))
