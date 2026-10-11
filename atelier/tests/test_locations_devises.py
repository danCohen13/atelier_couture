"""Locations : devise par contrat (shekel par défaut, euro possible) et recette de location dans les finances."""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from atelier.models import Client, Location, RobeLocation


class LocationsTestCase(TestCase):
    def setUp(self):
        User.objects.create_user('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(nom='Dupont', prenom='Claire')
        self.jour = datetime.date.today()
        self.stock = RobeLocation.objects.create(
            reference_stock='LOC-001', nom_modele='Aurore', taille='38', couleur='Ivoire',
            prix_location_defaut=Decimal('300.00'), caution_defaut=Decimal('500.00'),
        )

    def contrat(self, prix='300.00', caution='500.00', devise='ILS', statut='RESERVEE', jours=0, reference=None):
        stock = self.stock
        if reference:
            stock = RobeLocation.objects.create(
                reference_stock=reference, nom_modele=f'Modèle {reference}', taille='40', couleur='Noir',
                prix_location_defaut=prix, caution_defaut=caution,
            )
        debut = self.jour + datetime.timedelta(days=jours)
        return Location.objects.create(
            client=self.cliente, robe_location=stock, date_debut=debut,
            date_fin_prevue=debut + datetime.timedelta(days=3),
            prix_convenu=Decimal(prix), caution_montant=Decimal(caution), devise=devise, statut=statut,
        )


class DeviseDesLocationsTests(LocationsTestCase):
    def test_le_shekel_est_la_devise_par_defaut(self):
        self.assertEqual(self.stock.devise, 'ILS')
        self.assertEqual(self.contrat().devise, 'ILS')
        self.assertEqual(self.contrat(reference='LOC-002').symbole_devise, '₪')

    def test_l_euro_reste_possible_a_la_creation_d_un_contrat(self):
        r = self.client.post(reverse('creer_location'), {
            'client': self.cliente.pk, 'robe_location': self.stock.pk,
            'date_debut': (self.jour + datetime.timedelta(days=10)).strftime('%d/%m/%Y'),
            'date_fin_prevue': (self.jour + datetime.timedelta(days=13)).strftime('%d/%m/%Y'),
            'devise': 'EUR', 'prix_convenu': '250.00', 'caution_montant': '400.00',
            'caution_statut': 'NON_DEPOSEE', 'delai_tampon_jours': 2, 'statut': 'RESERVEE',
        })
        self.assertRedirects(r, reverse('tableau_bord_locations'))
        loc = Location.objects.get()
        self.assertEqual(loc.devise, 'EUR')
        self.assertEqual(loc.symbole_devise, '€')

    def test_le_formulaire_propose_le_shekel_par_defaut_et_les_autres_devises(self):
        form = self.client.get(reverse('creer_location')).context['form']
        self.assertEqual(form['devise'].value(), 'ILS')
        self.assertEqual({code for code, _ in form.fields['devise'].choices}, {'ILS', 'EUR', 'USD'})

    def test_sans_devise_envoyee_le_shekel_s_applique(self):
        self.client.post(reverse('creer_location'), {
            'client': self.cliente.pk, 'robe_location': self.stock.pk,
            'date_debut': (self.jour + datetime.timedelta(days=10)).strftime('%d/%m/%Y'),
            'date_fin_prevue': (self.jour + datetime.timedelta(days=13)).strftime('%d/%m/%Y'),
            'prix_convenu': '250.00', 'caution_montant': '400.00',
            'caution_statut': 'NON_DEPOSEE', 'delai_tampon_jours': 2, 'statut': 'RESERVEE',
        })
        self.assertEqual(Location.objects.get().devise, 'ILS')

    def test_la_devise_de_la_robe_de_stock_prerempli_le_contrat(self):
        stock_euro = RobeLocation.objects.create(
            reference_stock='LOC-EUR', nom_modele='Importée', taille='36', couleur='Bleu',
            prix_location_defaut=Decimal('200.00'), caution_defaut=Decimal('300.00'), devise='EUR',
        )
        form = self.client.get(reverse('creer_location'), {'robe_id': stock_euro.pk}).context['form']
        self.assertEqual(form.initial['devise'], 'EUR')

    def test_ajout_d_une_robe_au_stock_en_euros(self):
        self.client.post(reverse('ajouter_robe_location'), {
            'reference_stock': 'LOC-777', 'nom_modele': 'Étoile', 'taille': '38', 'couleur': 'Rouge',
            'devise': 'EUR', 'prix_location_defaut': '150.00', 'caution_defaut': '200.00',
            'statut_physique': 'DISPONIBLE',
        })
        self.assertEqual(RobeLocation.objects.get(reference_stock='LOC-777').devise, 'EUR')

    def test_les_ecrans_affichent_le_symbole_du_contrat(self):
        self.contrat(devise='ILS', reference='LOC-ILS')
        self.contrat(prix='123.00', caution='456.00', devise='EUR', reference='LOC-EUR', jours=20)
        page = self.client.get(reverse('tableau_bord_locations')).content.decode()
        self.assertIn('123,00 €', page)
        self.assertIn('300,00 ₪', page)
        self.assertNotIn('300,00 €', page)

    def test_le_catalogue_affiche_la_devise_de_la_robe(self):
        RobeLocation.objects.create(
            reference_stock='LOC-USD', nom_modele='Dollar', taille='38', couleur='Vert',
            prix_location_defaut=Decimal('99.00'), caution_defaut=Decimal('120.00'), devise='USD',
        )
        page = self.client.get(reverse('catalogue_location')).content.decode()
        self.assertIn('99,00 $', page)
        self.assertIn('300,00 ₪', page)

    def test_le_planning_affiche_le_symbole_du_contrat(self):
        self.contrat(prix='123.00', caution='456.00', devise='EUR')
        debut = self.jour - datetime.timedelta(days=5)
        fin = self.jour + datetime.timedelta(days=30)
        evenements = self.client.get(reverse('api_planning_evenements'), {
            'start': debut.isoformat(), 'end': fin.isoformat(),
        }).json()
        lignes = dict(map(tuple, evenements[0]['extendedProps']['lignes']))
        self.assertEqual(lignes['Tarif convenu'], '123.00 €')
        self.assertTrue(lignes['Caution'].startswith('456.00 €'))


class LocationsDansLesFinancesTests(LocationsTestCase):
    def finances(self, **params):
        return self.client.get(reverse('finances'), params).context

    def lignes(self, ctx):
        return [l for g in ctx['groupes'] for l in g['lignes']]

    def test_le_prix_de_location_est_une_recette_sans_la_caution(self):
        self.contrat(prix='300.00', caution='500.00')
        ctx = self.finances()
        self.assertEqual(ctx['total_recettes'], Decimal('300.00'))  # et non 800
        self.assertEqual(ctx['total_depenses'], 0)
        self.assertEqual(ctx['benefice_net'], Decimal('300.00'))

    def test_la_ligne_est_automatique_et_decrite(self):
        loc = self.contrat()
        (ligne,) = self.lignes(self.finances())
        self.assertEqual(ligne.type, 'RECETTE')
        self.assertEqual(ligne.get_categorie_display(), 'Location de robe (auto)')
        self.assertTrue(ligne.auto)
        self.assertEqual(ligne.date, loc.date_debut)  # recette datée du retrait de la robe
        self.assertIn('LOC-001', ligne.designation)
        self.assertIn('Aurore', ligne.designation)
        self.assertIn('DUPONT Claire', ligne.designation)
        self.assertEqual(ligne.montant, Decimal('300.00'))

    def test_une_location_annulee_n_est_pas_comptee(self):
        self.contrat(statut='ANNULEE')
        ctx = self.finances()
        self.assertEqual(ctx['total_recettes'], 0)
        self.assertEqual(self.lignes(ctx), [])

    def test_tous_les_autres_statuts_sont_comptes(self):
        for i, statut in enumerate(('RESERVEE', 'EN_COURS', 'EN_RETARD', 'TERMINEE')):
            self.contrat(prix='100.00', statut=statut, reference=f'LOC-S{i}')
        self.assertEqual(self.finances()['total_recettes'], Decimal('400.00'))

    def test_une_location_en_euros_va_dans_le_bloc_des_autres_devises(self):
        self.contrat(prix='300.00', devise='ILS')
        self.contrat(prix='200.00', caution='700.00', devise='EUR', reference='LOC-EUR')
        ctx = self.finances()
        self.assertEqual(ctx['total_recettes'], Decimal('300.00'))  # jamais d'addition ₪ + €
        (euro,) = ctx['autres_bilans']
        self.assertEqual((euro['devise'], euro['recettes']), ('EUR', Decimal('200.00')))

    def test_le_filtre_de_periode_s_applique_a_la_date_de_retrait(self):
        self.contrat(prix='100.00', jours=0, reference='LOC-A')
        self.contrat(prix='900.00', jours=-400, reference='LOC-B')
        self.assertEqual(self.finances(periode='tout')['total_recettes'], Decimal('1000.00'))
        self.assertEqual(self.finances(periode='jour')['total_recettes'], Decimal('100.00'))

    def test_le_graphe_inclut_les_locations_en_shekels(self):
        self.contrat(prix='300.00')
        self.contrat(prix='500.00', devise='EUR', reference='LOC-EUR')
        serie = self.finances()['chart_data']['annee']
        self.assertEqual(sum(serie['recettes']), 300.0)

    def test_page_finances_affiche_la_ligne_de_location(self):
        self.contrat()
        page = self.client.get(reverse('finances'))
        self.assertContains(page, 'Location de robe (auto)')
        self.assertContains(page, '300,00')
