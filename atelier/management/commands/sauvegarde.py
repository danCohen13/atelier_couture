"""Sauvegarde chiffrée de la base (à planifier chaque nuit : voir docs/SAUVEGARDES.md)."""
from django.core.management.base import BaseCommand, CommandError

from atelier.services import sauvegarde as svc


class Command(BaseCommand):
    help = "Crée une sauvegarde chiffrée de la base et applique la rotation (14 jours + 12 mois)."

    def add_arguments(self, parser):
        parser.add_argument('--dossier', help="Écrit dans ce dossier local au lieu du stockage S3.")
        parser.add_argument('--generer-cle', action='store_true', help="Affiche une nouvelle clé de chiffrement et s'arrête.")

    def handle(self, *args, **options):
        if options['generer_cle']:
            self.stdout.write(svc.generer_cle())
            return
        try:
            nom, octets, supprimes = svc.sauvegarder(svc.stockage(options['dossier']))
        except svc.ErreurSauvegarde as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde {nom} ({octets // 1024} Ko) ; {len(supprimes)} ancienne(s) supprimée(s)."))
