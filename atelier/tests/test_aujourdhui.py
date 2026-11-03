import datetime
from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from atelier.models import Adhesion, Atelier, Client, Location, Paiement, Robe, RobeLocation, Tache
from atelier.services.aujourdhui import tableau_du_jour
from atelier.tests.outils import utilisateur_test

JOUR = datetime.timedelta(days=1)


class Base(TestCase):
    def setUp(self):
        self.a = Atelier.objects.create(nom='Atelier A')
        self.b = Atelier.objects.create(nom='Atelier B')
        self.aujourdhui = timezone.localdate()
        self.cliente = Client.objects.create(atelier=self.a, nom='Levi', prenom='Dana', telephone='+972501234567')
        self.robe_stock = RobeLocation.objects.create(
            atelier=self.a, reference_stock='LOC-1', nom_modele='Aurore', taille='38', couleur='Ivoire',
            prix_location_defaut=600, caution_defaut=1000)

    def robe(self, jours, prix=1000, atelier=None, taches=0, faites=0):
        atelier = atelier or self.a
        client = self.cliente if atelier == self.a else Client.objects.create(atelier=atelier, nom='Autre', prenom='X')
        robe = Robe.objects.create(
            atelier=atelier, client=client, nom_modele=f'Robe {jours}', date_commencement=self.aujourdhui - 30 * JOUR,
            date_livraison=self.aujourdhui + jours * JOUR, prix_total=prix)
        for i in range(taches):
            Tache.objects.create(atelier=atelier, robe=robe, libelle=f't{i}', est_faite=i < faites)
        return robe

    def location(self, debut, fin, statut='RESERVEE', **kw):
        return Location.objects.create(
            atelier=self.a, client=self.cliente, robe_location=self.robe_stock, date_debut=self.aujourdhui + debut * JOUR,
            date_fin_prevue=self.aujourdhui + fin * JOUR, statut=statut, prix_convenu=600, caution_montant=1000, **kw)

    def genres(self, cle, avec_paiements=False):
        sections = {s.cle: s for s in tableau_du_jour(self.a, self.aujourdhui)['sections']}
        genres = sorted(e.genre for e in sections[cle].elements) if cle in sections else []
        return genres if avec_paiements else [g for g in genres if g != 'paiement_en_retard']


class ContenuTests(Base):
    def test_livraison_en_retard_aujourdhui_et_semaine(self):
        self.robe(-3, prix=0)
        self.robe(0, prix=0)
        self.robe(4, prix=0)
        self.robe(30, prix=0)           # trop loin : absente
        self.assertEqual(self.genres('urgent'), ['livraison_en_retard'])
        self.assertEqual(self.genres('aujourdhui'), ['livraison'])
        self.assertEqual(self.genres('semaine'), ['livraison'])

    def test_robe_terminee_n_apparait_pas(self):
        self.robe(-5, prix=0, taches=2, faites=2)
        self.assertEqual(tableau_du_jour(self.a, self.aujourdhui)['vide'], True)

    def test_etapes_restantes_dans_le_detail(self):
        self.robe(-1, prix=0, taches=4, faites=1)
        e = tableau_du_jour(self.a, self.aujourdhui)['sections'][0].elements[0]
        self.assertIn('3', e.detail)

    def test_locations(self):
        self.location(-2, 0, statut='EN_COURS')              # retour attendu aujourd'hui
        self.location(-5, -2, statut='EN_COURS')             # retour en retard
        self.location(-1, 3, statut='RESERVEE')              # retrait manqué
        self.location(0, 2, statut='RESERVEE')               # retrait aujourd'hui
        self.location(3, 5, statut='RESERVEE')               # retrait dans la semaine
        self.location(-9, -7, statut='ANNULEE')              # ignorée
        self.assertEqual(self.genres('urgent'), ['retour_en_retard', 'retrait_manque'])
        self.assertEqual(self.genres('aujourdhui'), ['retour', 'retrait'])
        self.assertEqual(self.genres('semaine'), ['retrait'])

    def test_paiement_en_retard_et_ordre_des_sections(self):
        robe = self.robe(-2, prix=1000)
        Paiement.objects.create(atelier=self.a, robe=robe, montant=Decimal('400'), date=self.aujourdhui)
        urgent = tableau_du_jour(self.a, self.aujourdhui)['sections'][0]
        self.assertEqual(urgent.cle, 'urgent')
        genres = [e.genre for e in urgent.elements]
        self.assertIn('paiement_en_retard', genres)
        paiement = next(e for e in urgent.elements if e.genre == 'paiement_en_retard')
        self.assertIn('600', paiement.detail)  # reste à payer = 1000 − 400

    def test_caution_a_restituer(self):
        self.location(-6, -4, statut='TERMINEE', caution_statut='ENREGISTREE', date_retour_effectif=self.aujourdhui - 4 * JOUR)
        self.assertEqual(self.genres('urgent'), ['caution_a_restituer'])

    def test_ecart_en_jours(self):
        self.robe(-3, prix=0)
        self.assertEqual(tableau_du_jour(self.a, self.aujourdhui)['sections'][0].elements[0].ecart, -3)

    def test_rien_a_signaler(self):
        resultat = tableau_du_jour(self.a, self.aujourdhui)
        self.assertTrue(resultat['vide'])
        self.assertEqual(resultat['sections'], [])


class IsolationTests(Base):
    def test_les_donnees_d_un_autre_atelier_n_apparaissent_pas(self):
        self.robe(-3, prix=500, atelier=self.b)
        self.assertTrue(tableau_du_jour(self.a, self.aujourdhui)['vide'])
        self.assertFalse(tableau_du_jour(self.b, self.aujourdhui)['vide'])


class PageTests(Base):
    def setUp(self):
        super().setUp()
        self.user = utilisateur_test('dana', password='x-motdepasse-123', atelier=self.a)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'fr'
        self.client.login(username='dana', password='x-motdepasse-123')

    def test_connexion_requise(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('aujourdhui')).status_code, 302)

    def test_apres_connexion_on_arrive_sur_aujourdhui(self):
        self.client.logout()
        r = self.client.post(reverse('login'), {'username': 'dana', 'password': 'x-motdepasse-123'})
        self.assertRedirects(r, reverse('aujourdhui'), fetch_redirect_response=False)

    def test_page_francais(self):
        self.robe(-3, prix=0)
        r = self.client.get(reverse('aujourdhui'))
        self.assertContains(r, 'À traiter maintenant')
        self.assertContains(r, 'Livraison en retard')
        self.assertContains(r, '3 jours de retard')
        self.assertContains(r, 'href="tel:+972501234567"')
        self.assertContains(r, 'dir="ltr"')  # un numéro de téléphone reste de gauche à droite, même en hébreu

    def test_page_vide(self):
        self.assertContains(self.client.get(reverse('aujourdhui')), "Rien d'urgent")

    def test_page_hebreu(self):
        Adhesion.objects.filter(user=self.user).update(langue='he')
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'he'
        self.robe(-3, prix=0)
        r = self.client.get(reverse('aujourdhui'))
        self.assertContains(r, 'dir="rtl"')
        self.assertContains(r, 'לטיפול מיידי')
        self.assertContains(r, 'איחור של 3 ימים')
        self.assertNotContains(r, 'À traiter')

    def test_lien_dans_le_menu(self):
        self.assertContains(self.client.get(reverse('dashboard')), reverse('aujourdhui'))

    def test_un_autre_atelier_ne_voit_pas_mes_donnees(self):
        self.robe(-3, prix=0)
        utilisateur_test('bob', password='x-motdepasse-123', atelier=self.b)
        autre = self.client_class()
        autre.cookies[settings.LANGUAGE_COOKIE_NAME] = 'fr'
        autre.login(username='bob', password='x-motdepasse-123')
        self.assertNotContains(autre.get(reverse('aujourdhui')), 'Levi')
