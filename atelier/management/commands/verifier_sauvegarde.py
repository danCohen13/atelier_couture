"""Contrôle la dernière sauvegarde : récente, lisible avec la clé, non vide. Code de sortie 1 sinon (alerte)."""
import datetime

from django.core.management.base import BaseCommand, CommandError

from atelier.services import sauvegarde as svc


class Command(BaseCommand):
    help = "Vérifie que la dernière sauvegarde est récente et déchiffrable."

    def add_arguments(self, parser):
        parser.add_argument('--dossier')
        parser.add_argument('--heures', type=int, default=36, help="Âge maximal accepté (défaut : 36 h).")

    def handle(self, *args, **options):
        try:
            depot = svc.stockage(options['dossier'])
            noms = depot.lister()
            if not noms:
                raise CommandError("Aucune sauvegarde trouvée.")
            dernier = noms[-1]
            age = datetime.datetime.now(datetime.timezone.utc) - svc.date_du_fichier(dernier)
            if age > datetime.timedelta(hours=options['heures']):
                raise CommandError(f"Dernière sauvegarde trop ancienne : {dernier} ({age.days} j {age.seconds // 3600} h).")
            comptes = svc.compter(svc.dechiffrer(depot.lire(dernier)))
        except svc.ErreurSauvegarde as exc:
            raise CommandError(str(exc)) from exc
        if not comptes.get('auth.user'):
            raise CommandError(f"{dernier} ne contient aucun compte : sauvegarde suspecte.")
        resume = ', '.join(f"{m.split('.')[-1]}={n}" for m, n in sorted(comptes.items()) if m.startswith('atelier.'))
        self.stdout.write(self.style.SUCCESS(f"{dernier} : lisible. {resume}"))
