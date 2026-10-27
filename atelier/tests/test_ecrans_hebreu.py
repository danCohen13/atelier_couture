"""Les écrans internes, rendus en hébreu, ne doivent plus contenir de texte français visible."""
import re

from django.test import TestCase
from django.urls import reverse

from atelier.models import Adhesion
from atelier.tests.outils import utilisateur_test

# Mots français courants des interfaces : leur présence dans le texte visible trahit une chaîne non traduite.
MOTS_FRANCAIS = re.compile(
    r"\b(Enregistrer|Annuler|Supprimer|Modifier|Nouvelle?|Ajouter|Retour|Aucune?|Rechercher|Filtrer|Total|"
    r"Mensurations|Paiements?|Cautions?|Robes?|Clientes?|Finances|Planning|Confidentialité|Bénéfice|"
    r"Location|Dépenses?|Tableau de bord|Voir|Valider|Louer)\b")

PAGES = ['dashboard', 'liste_clientes', 'ajouter_client', 'ajouter_robe', 'finances', 'ajouter_transaction',
         'impayes', 'rentabilite', 'depenses_recurrentes', 'parametres_finance', 'catalogue_location',
         'ajouter_robe_location', 'tableau_bord_locations', 'creer_location', 'planning', 'confidentialite']


def texte_visible(html):
    html = re.sub(r'<(script|style)\b.*?</\1>', '', html, flags=re.S)
    html = re.sub(r'<[^>]+>', ' ', html)
    return html


class EcransEnHebreuTests(TestCase):
    def setUp(self):
        user = utilisateur_test('hebraique', password='motdepasse123')
        Adhesion.objects.filter(user=user).update(langue='he')
        self.client.login(username='hebraique', password='motdepasse123')

    def test_aucun_texte_francais_visible(self):
        for nom in PAGES:
            with self.subTest(page=nom):
                reponse = self.client.get(reverse(nom))
                self.assertEqual(reponse.status_code, 200)
                html = reponse.content.decode()
                self.assertIn('dir="rtl"', html)
                restes = MOTS_FRANCAIS.findall(texte_visible(html))
                self.assertEqual(restes, [], f"Texte français restant sur {nom}")
