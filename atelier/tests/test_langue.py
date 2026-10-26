"""Hébreu par défaut / français au choix, et affichage de droite à gauche."""
import pathlib
import re

import polib
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from atelier.models import Adhesion, Atelier

MOT_DE_PASSE = 'motdepasse123'


class LangueTests(TestCase):
    def setUp(self):
        self.atelier = Atelier.objects.create(nom='Atelier test')
        self.user = User.objects.create_user('lea', password=MOT_DE_PASSE)
        self.adhesion = Adhesion.objects.create(user=self.user, atelier=self.atelier)

    def test_hebreu_par_defaut_meme_si_le_navigateur_est_en_francais(self):
        reponse = self.client.get(reverse('login'), headers={'accept-language': 'fr-FR,fr;q=0.9'})
        self.assertContains(reponse, 'lang="he"')
        self.assertContains(reponse, 'dir="rtl"')
        self.assertEqual(reponse.headers['Content-Language'], 'he')

    def test_menu_traduit_en_hebreu(self):
        self.client.login(username='lea', password=MOT_DE_PASSE)
        reponse = self.client.get(reverse('liste_clientes'))
        self.assertContains(reponse, 'לוח זמנים')      # Planning
        self.assertContains(reponse, 'התנתקות')        # Déconnexion
        self.assertNotContains(reponse, 'Planning')

    def test_choix_du_francais(self):
        reponse = self.client.post(reverse('changer_langue'), {'langue': 'fr', 'next': reverse('login')})
        self.assertRedirects(reponse, reverse('login'), fetch_redirect_response=False)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'fr')
        page = self.client.get(reverse('login'))
        self.assertContains(page, 'lang="fr"')
        self.assertContains(page, 'dir="ltr"')

    def test_le_choix_est_enregistre_sur_le_compte_et_suit_l_utilisatrice(self):
        self.client.login(username='lea', password=MOT_DE_PASSE)
        self.client.post(reverse('changer_langue'), {'langue': 'fr'})
        self.adhesion.refresh_from_db()
        self.assertEqual(self.adhesion.langue, 'fr')
        # Autre appareil : pas de cookie, mais le compte se souvient.
        autre = self.client_class()
        autre.login(username='lea', password=MOT_DE_PASSE)
        reponse = autre.get(reverse('liste_clientes'))
        self.assertContains(reponse, 'lang="fr"')
        self.assertContains(reponse, 'Planning')
        self.assertEqual(autre.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'fr')

    def test_langue_inconnue_ignoree(self):
        self.client.post(reverse('changer_langue'), {'langue': 'xx'})
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, self.client.cookies)
        self.assertContains(self.client.get(reverse('login')), 'lang="he"')

    def test_redirection_externe_refusee(self):
        reponse = self.client.post(reverse('changer_langue'), {'langue': 'fr', 'next': 'https://evil.example/'})
        self.assertEqual(reponse.status_code, 302)
        self.assertFalse(reponse.url.startswith('http'))

    def test_changement_de_langue_en_post_seulement(self):
        self.assertEqual(self.client.get(reverse('changer_langue')).status_code, 405)

    def test_selecteur_de_langue_dans_l_en_tete(self):
        reponse = self.client.get(reverse('login'))
        self.assertContains(reponse, 'עברית')
        self.assertContains(reponse, 'Français')


class CatalogueTests(TestCase):
    RACINE = pathlib.Path(__file__).resolve().parent.parent

    def test_toutes_les_traductions_hebraiques_sont_remplies_et_compilees(self):
        po = polib.pofile(str(self.RACINE / 'locale/he/LC_MESSAGES/django.po'))
        manquantes = [e.msgid for e in po if not e.msgstr or 'fuzzy' in e.flags]
        self.assertEqual(manquantes, [], "Traductions hébraïques manquantes (puis relancer compilemessages)")
        mo = polib.mofile(str(self.RACINE / 'locale/he/LC_MESSAGES/django.mo'))
        self.assertEqual({e.msgid: e.msgstr for e in mo}, {e.msgid: e.msgstr for e in po},
                         "django.mo n'est pas à jour : python manage.py compilemessages")

    def test_catalogue_francais_complet(self):
        """Sans entrée française, Django retomberait sur l'hébreu (langue par défaut)."""
        he = polib.pofile(str(self.RACINE / 'locale/he/LC_MESSAGES/django.po'))
        fr = polib.mofile(str(self.RACINE / 'locale/fr/LC_MESSAGES/django.mo'))
        absents = {e.msgid for e in he} - {e.msgid for e in fr if e.msgstr == e.msgid}
        self.assertEqual(absents, set(), "Catalogue français incomplet : python manage.py traductions")


class CssDroiteAGaucheTests(TestCase):
    """Le CSS n'utilise que des propriétés logiques : sinon la page ne se retourne pas en hébreu."""

    def test_pas_de_propriete_gauche_droite(self):
        interdit = re.compile(
            r'(margin|padding|border)-(left|right)\b|text-align:\s*(left|right)|(?<![\w-])(left|right):|float:\s*(left|right)')
        for css in (pathlib.Path(__file__).resolve().parent.parent / 'static/atelier/css').glob('*.css'):
            for numero, ligne in enumerate(css.read_text(encoding='utf-8').splitlines(), 1):
                self.assertIsNone(interdit.search(ligne), f"{css.name}:{numero} {ligne.strip()}")
