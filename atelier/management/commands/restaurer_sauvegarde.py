"""Restaure une sauvegarde dans une base VIDE (nouvelle base Neon, ou base locale pour un exercice)."""
import os
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from atelier.services import sauvegarde as svc


class Command(BaseCommand):
    help = "Restaure une sauvegarde chiffrée (dernière par défaut) dans une base vide."

    def add_arguments(self, parser):
        parser.add_argument('--dossier', help="Dossier local au lieu du stockage S3.")
        parser.add_argument('--fichier', help="Nom du fichier à restaurer (défaut : le plus récent).")
        parser.add_argument('--confirmer', action='store_true', help="Obligatoire : confirme que la base cible est la bonne.")

    def handle(self, *args, **options):
        if not options['confirmer']:
            raise CommandError("Ajoute --confirmer après avoir vérifié la base visée (DATABASE_URL).")
        if User.objects.exists():
            raise CommandError("La base cible n'est pas vide (des comptes existent). Restaure dans une base neuve : "
                               "on n'écrase jamais des données vivantes avec cette commande.")
        try:
            depot = svc.stockage(options['dossier'])
            nom = options['fichier'] or (depot.lister() or [None])[-1]
            if not nom:
                raise CommandError("Aucune sauvegarde trouvée.")
            texte = svc.dechiffrer(depot.lire(nom))
        except svc.ErreurSauvegarde as exc:
            raise CommandError(str(exc)) from exc
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, 'sauvegarde.json')
            with open(chemin, 'w', encoding='utf-8') as f:
                f.write(texte)
            call_command('loaddata', chemin, verbosity=0)
        comptes = svc.compter(texte)
        self.stdout.write(self.style.SUCCESS(
            f"{nom} restaurée : {sum(comptes.values())} enregistrements dans {len(comptes)} tables."))
