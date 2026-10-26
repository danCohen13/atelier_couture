"""Outil de développement : met à jour les catalogues de traduction (hébreu + français).

Les textes sources du code sont en français. Le catalogue français doit exister (msgstr = msgid) :
sinon Django retomberait sur l'hébreu, la langue par défaut, pour tout texte absent du catalogue français.

    python manage.py traductions        # extrait les textes, complète le français, compile
Puis traduire les entrées vides de atelier/locale/he/LC_MESSAGES/django.po.
"""
import os

import polib
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Extrait les textes à traduire, complète le catalogue français et compile les catalogues."

    def handle(self, *args, **options):
        racine = os.path.join(os.getcwd(), 'atelier')
        os.chdir(racine)
        try:
            call_command('makemessages', locale=['he', 'fr'], no_location=True, no_obsolete=True, verbosity=0)
            # msgmerge « devine » parfois une traduction voisine (marquée fuzzy) : jamais fiable, on la vide.
            for langue in ('he', 'fr'):
                chemin = os.path.join('locale', langue, 'LC_MESSAGES', 'django.po')
                catalogue = polib.pofile(chemin)
                for entree in catalogue:
                    if 'fuzzy' in entree.flags:
                        entree.flags.remove('fuzzy')
                        entree.msgstr = ''
                catalogue.save()
            chemin_fr = os.path.join('locale', 'fr', 'LC_MESSAGES', 'django.po')
            catalogue = polib.pofile(chemin_fr)
            for entree in catalogue:
                entree.msgstr = entree.msgid
            catalogue.metadata['Language'] = 'fr'
            catalogue.save()
            call_command('compilemessages', verbosity=0)
        finally:
            os.chdir(os.path.dirname(racine))
        vides = [e.msgid for e in polib.pofile(os.path.join(racine, 'locale', 'he', 'LC_MESSAGES', 'django.po')) if not e.msgstr]
        self.stdout.write(self.style.SUCCESS(f"Catalogues à jour. Entrées hébraïques à traduire : {len(vides)}"))
