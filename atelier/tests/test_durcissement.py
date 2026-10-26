"""Tests du durcissement : déconnexion, lien admin, messages, blocage Axes, finances multi-devises, fuseau."""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from atelier.models import Client, Robe, RobeLocation, Transaction
from atelier.tests.outils import atelier_test, utilisateur_test

BACKENDS_AVEC_AXES = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]


class DeconnexionTests(TestCase):
    def setUp(self):
        utilisateur_test('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')

    def test_la_deconnexion_par_simple_lien_est_refusee(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_la_deconnexion_en_post_fonctionne(self):
        r = self.client.post(reverse('logout'))
        self.assertRedirects(r, reverse('login'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_le_bouton_de_deconnexion_est_un_formulaire_post(self):
        page = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn(f'method="POST" action="{reverse("logout")}"', page)


class LienAdministrationTests(TestCase):
    def test_pas_de_lien_admin_pour_un_visiteur_anonyme(self):
        page = self.client.get(reverse('login')).content.decode()
        self.assertNotIn("Accéder à l'admin", page)
        self.assertNotIn('href="/admin/"', page)

    def test_pas_de_lien_admin_pour_un_compte_sans_droit(self):
        utilisateur_test('simple', password='motdepasse123')
        self.client.login(username='simple', password='motdepasse123')
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Administration')

    def test_lien_admin_pour_un_compte_staff(self):
        utilisateur_test('chef', password='motdepasse123', is_staff=True)
        self.client.login(username='chef', password='motdepasse123')
        self.assertContains(self.client.get(reverse('dashboard')), reverse('admin:index'))

    def test_pages_privees_non_indexables(self):
        self.assertContains(self.client.get(reverse('login')), 'noindex')


class MessagesTests(TestCase):
    def setUp(self):
        utilisateur_test('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')

    def test_le_message_de_succes_s_affiche_apres_ajout_au_stock(self):
        r = self.client.post(reverse('ajouter_robe_location'), {
            'reference_stock': 'LOC-001', 'nom_modele': 'Aurore', 'taille': '38', 'couleur': 'Ivoire',
            'prix_location_defaut': '300.00', 'caution_defaut': '500.00', 'statut_physique': 'DISPONIBLE',
        }, follow=True)
        self.assertContains(r, 'LOC-001 a été ajoutée au stock')
        self.assertContains(r, 'form-alert--success')

    def test_le_message_ne_s_affiche_qu_une_fois(self):
        self.client.post(reverse('ajouter_robe_location'), {
            'reference_stock': 'LOC-002', 'nom_modele': 'Aube', 'taille': '40', 'couleur': 'Rose',
            'prix_location_defaut': '300.00', 'caution_defaut': '500.00', 'statut_physique': 'DISPONIBLE',
        }, follow=True)
        self.assertNotContains(self.client.get(reverse('catalogue_location')), 'a été ajoutée au stock')

    def test_pas_de_message_en_double_sur_les_pages_de_reinitialisation(self):
        r = self.client.post(reverse('demander_code_reset'), {'email': 'nobody@example.com'}, follow=True)
        self.assertEqual(r.content.decode().count("Si un compte correspond"), 1)

    def test_le_succes_du_changement_de_mot_de_passe_s_affiche_sur_la_page_de_connexion(self):
        session = self.client.session
        session['reset_user_id'] = User.objects.get().id
        session['code_verifie'] = True
        session.save()
        r = self.client.post(reverse('nouveau_mot_de_passe'),
                             {'password': 'NouveauMdp456!', 'password_confirm': 'NouveauMdp456!'}, follow=True)
        self.assertContains(r, 'modifié avec succès')


@override_settings(AUTHENTICATION_BACKENDS=BACKENDS_AVEC_AXES)
class BlocageApresEchecsTests(TestCase):
    """django-axes : 5 mauvais mots de passe bloquent la connexion pendant une heure."""

    def setUp(self):
        utilisateur_test('atelier', password='BonMotDePasse123!')

    def tenter(self, mot_de_passe, username='atelier'):
        return self.client.post(reverse('login'), {'username': username, 'password': mot_de_passe})

    def test_blocage_des_le_cinquieme_echec_meme_avec_le_bon_mot_de_passe(self):
        for _ in range(4):
            self.assertEqual(self.tenter('mauvais').status_code, 200)
        self.assertEqual(self.tenter('mauvais').status_code, 429)  # le 5e échec déclenche le blocage

        r = self.tenter('BonMotDePasse123!')
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, 'temporairement bloqué', status_code=429)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_une_connexion_normale_n_est_pas_bloquee(self):
        self.tenter('mauvais')
        self.assertEqual(self.tenter('BonMotDePasse123!').status_code, 302)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_les_echecs_sont_remis_a_zero_apres_une_reussite(self):
        for _ in range(4):
            self.tenter('mauvais')
        self.assertEqual(self.tenter('BonMotDePasse123!').status_code, 302)
        self.client.logout()
        for _ in range(4):
            self.assertEqual(self.tenter('mauvais').status_code, 200)

    def test_un_autre_identifiant_n_est_pas_affecte(self):
        utilisateur_test('autre', password='BonMotDePasse123!')
        for _ in range(5):
            self.tenter('mauvais')
        self.assertEqual(self.tenter('BonMotDePasse123!', username='autre').status_code, 302)


class FinancesMultiDevisesTests(TestCase):
    def setUp(self):
        utilisateur_test('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(atelier=atelier_test(), nom='Dupont', prenom='Claire')
        self.jour = datetime.date.today()

    def robe(self, nom, prix, devise, tissu=0):
        return Robe.objects.create(
            client=self.cliente, nom_modele=nom, date_commencement=self.jour, date_livraison=self.jour,
            prix_total=Decimal(prix), cout_tissu=Decimal(tissu), devise=devise,
        )

    def test_les_devises_ne_sont_jamais_additionnees(self):
        self.robe('Robe shekel', '500.00', 'ILS', tissu='100.00')
        self.robe('Robe euro', '1000.00', 'EUR', tissu='200.00')
        self.robe('Robe dollar', '300.00', 'USD')

        ctx = self.client.get(reverse('finances')).context
        self.assertEqual(ctx['total_recettes'], Decimal('500.00'))
        self.assertEqual(ctx['total_depenses'], Decimal('100.00'))
        self.assertEqual(ctx['benefice_net'], Decimal('400.00'))

        autres = {b['devise']: b for b in ctx['autres_bilans']}
        self.assertEqual(set(autres), {'EUR', 'USD'})
        self.assertEqual(autres['EUR']['recettes'], Decimal('1000.00'))
        self.assertEqual(autres['EUR']['depenses'], Decimal('200.00'))
        self.assertEqual(autres['EUR']['benefice'], Decimal('800.00'))
        self.assertEqual(autres['USD']['symbole'], '$')

    def test_le_graphe_ne_contient_que_la_devise_de_l_atelier(self):
        self.robe('Robe shekel', '500.00', 'ILS')
        self.robe('Robe euro', '1000.00', 'EUR')
        serie = self.client.get(reverse('finances')).context['chart_data']['annee']
        self.assertEqual(sum(serie['recettes']), 500.0)

    def test_l_ecran_annonce_les_autres_devises(self):
        self.robe('Robe euro', '1000.00', 'EUR')
        page = self.client.get(reverse('finances'))
        self.assertContains(page, 'Autres devises')
        self.assertContains(page, '1\u00a0000,00 €')  # format français : espace des milliers, virgule décimale

    def test_pas_de_bloc_autres_devises_quand_tout_est_en_shekels(self):
        self.robe('Robe shekel', '500.00', 'ILS')
        self.assertNotContains(self.client.get(reverse('finances')), 'Autres devises')

    def test_les_operations_manuelles_sont_comptees_en_shekels(self):
        Transaction.objects.create(atelier=atelier_test(), type='DEPENSE', montant=Decimal('80.00'), categorie='FOURNITURES',
                                   designation='Fils', date=self.jour)
        ctx = self.client.get(reverse('finances')).context
        self.assertEqual(ctx['total_depenses'], Decimal('80.00'))
        self.assertEqual(ctx['autres_bilans'], [])


class DatesLocalesTests(TestCase):
    def test_jours_restants_utilise_la_date_locale_de_l_atelier(self):
        cliente = Client.objects.create(atelier=atelier_test(), nom='Dupont', prenom='Claire')
        robe = Robe.objects.create(
            client=cliente, nom_modele='Robe', date_commencement=datetime.date(2026, 10, 1),
            date_livraison=datetime.date(2026, 10, 14),
        )
        with mock.patch('django.utils.timezone.localdate', return_value=datetime.date(2026, 10, 11)):
            self.assertEqual(robe.jours_restants, 3)

    def test_une_location_est_en_retard_selon_la_date_locale(self):
        from atelier.models import Location
        cliente = Client.objects.create(atelier=atelier_test(), nom='Dupont', prenom='Claire')
        stock = RobeLocation.objects.create(atelier=atelier_test(), 
            reference_stock='LOC-9', nom_modele='M', taille='38', couleur='Noir',
            prix_location_defaut=100, caution_defaut=100,
        )
        loc = Location(client=cliente, robe_location=stock, date_debut=datetime.date(2026, 10, 1),
                       date_fin_prevue=datetime.date(2026, 10, 10), prix_convenu=100, caution_montant=100,
                       statut='EN_COURS')
        with mock.patch('django.utils.timezone.localdate', return_value=datetime.date(2026, 10, 11)):
            self.assertTrue(loc.est_en_retard)
        with mock.patch('django.utils.timezone.localdate', return_value=datetime.date(2026, 10, 10)):
            self.assertFalse(loc.est_en_retard)
