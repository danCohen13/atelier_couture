import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RACINE = Path(__file__).resolve().parents[2]


def charger_reglages(**env):
    """Importe config.settings dans un processus neuf (sans « test » dans argv) avec cet environnement."""
    environnement = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings as s; print(s.DEBUG, bool(s.SECRET_KEY))"],
        cwd=RACINE, env=environnement, capture_output=True, text=True,
    )


class ReglagesSecuriteTests(SimpleTestCase):
    """Les valeurs vides sont fournies explicitement : un fichier .env local ne peut pas les écraser."""

    def test_refuse_de_demarrer_sans_secret_key_hors_debug(self):
        r = charger_reglages(SECRET_KEY="", DEBUG="False")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr)

    def test_demarre_avec_une_secret_key_en_production(self):
        r = charger_reglages(SECRET_KEY="une-vraie-cle", DEBUG="False")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "False True")

    def test_cle_de_secours_uniquement_en_developpement(self):
        r = charger_reglages(SECRET_KEY="", DEBUG="True")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "True True")


class StockageStatiqueTests(SimpleTestCase):
    def test_pas_de_stockage_hashe_pendant_les_tests(self):
        """Sans quoi les tests exigeraient un `collectstatic` préalable (et échoueraient en bloc)."""
        self.assertNotIn("Manifest", settings.STORAGES["staticfiles"]["BACKEND"])
