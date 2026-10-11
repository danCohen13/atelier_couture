import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RACINE = Path(__file__).resolve().parents[2]


def charger_reglages(*, affiche="s.DEBUG, bool(s.SECRET_KEY)", **env):
    """
    Importe config.settings dans un processus neuf (sans « test » dans argv) avec cet
    environnement, et affiche l'expression `affiche` (où `s` désigne les réglages).
    """
    environnement = {"DATABASE_URL": "sqlite:///:memory:", **os.environ, **env}
    return subprocess.run(
        [sys.executable, "-c", f"import config.settings as s; print({affiche})"],
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


class DurcissementProductionTests(SimpleTestCase):
    """Réglages de sécurité : actifs en production, absents en développement."""

    PROD = {"DEBUG": "False", "SECRET_KEY": "une-vraie-cle"}
    LECTURE = ("s.SECURE_SSL_REDIRECT, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, "
               "s.SECURE_HSTS_SECONDS > 0, s.X_FRAME_OPTIONS")

    def test_https_force_en_production(self):
        r = charger_reglages(affiche=self.LECTURE, **self.PROD)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "True True True True DENY")

    def test_pas_de_redirection_https_en_developpement(self):
        r = charger_reglages(
            affiche="getattr(s, 'SECURE_SSL_REDIRECT', False), getattr(s, 'SESSION_COOKIE_SECURE', False)",
            DEBUG="True", SECRET_KEY="",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "False False")

    def test_base_de_donnees_obligatoire_en_production(self):
        r = charger_reglages(DATABASE_URL="", **self.PROD)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DATABASE_URL", r.stderr)

    def test_aucun_mot_de_passe_en_dur_dans_les_reglages(self):
        source = (RACINE / "config" / "settings.py").read_text(encoding="utf-8")
        for secret in ("admin1234", "b320f3001", "@gmail.com"):
            self.assertNotIn(secret, source)

    def test_url_admin_configurable(self):
        for saisie, attendu in (("", "admin/"), ("gestion-x7k2p", "gestion-x7k2p/"), ("/gestion-x7k2p/", "gestion-x7k2p/")):
            r = charger_reglages(affiche="s.ADMIN_URL", ADMIN_URL=saisie, **self.PROD)
            self.assertEqual(r.stdout.strip(), attendu, saisie)

    def test_domaine_personnalise_autorise_pour_les_formulaires(self):
        r = charger_reglages(
            affiche="'atelier.example.com' in s.ALLOWED_HOSTS, 'https://atelier.example.com' in s.CSRF_TRUSTED_ORIGINS",
            ALLOWED_HOSTS="atelier.example.com", **self.PROD,
        )
        self.assertEqual(r.stdout.strip(), "True True")

    def test_fuseau_horaire_de_l_atelier(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Jerusalem")


class StockageStatiqueTests(SimpleTestCase):
    def test_pas_de_stockage_hashe_pendant_les_tests(self):
        """Sans quoi les tests exigeraient un `collectstatic` préalable (et échoueraient en bloc)."""
        self.assertNotIn("Manifest", settings.STORAGES["staticfiles"]["BACKEND"])
