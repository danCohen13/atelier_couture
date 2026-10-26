"""Invite un nouvel atelier : affiche le lien d'inscription (valable 7 jours, usage unique).

    python manage.py inviter lea@example.com "Atelier Léa" [--envoyer] [--langue he|fr] [--jours 7]
"""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from atelier.invitations import envoyer_invitation, lien_invitation
from atelier.models import Invitation


class Command(BaseCommand):
    help = "Crée une invitation et affiche le lien à transmettre (affiché une seule fois)."

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('nom_atelier', nargs='?', default='')
        parser.add_argument('--envoyer', action='store_true', help="Envoyer aussi le lien par e-mail")
        parser.add_argument('--langue', default='he', choices=['he', 'fr'], help="Langue de l'e-mail")
        parser.add_argument('--jours', type=int, default=Invitation.DUREE_JOURS)

    def handle(self, *args, **options):
        try:
            invitation, jeton = Invitation.creer(options['email'], options['nom_atelier'], options['jours'])
        except ValidationError as erreur:
            raise CommandError(' '.join(erreur.messages)) from erreur
        self.stdout.write(lien_invitation(jeton))
        if options['envoyer']:
            if envoyer_invitation(invitation, jeton, options['langue']):
                self.stdout.write(self.style.SUCCESS(f"E-mail envoyé à {invitation.email}."))
            else:
                self.stderr.write(self.style.WARNING("L'e-mail n'a pas pu partir : transmettez le lien vous-même."))
