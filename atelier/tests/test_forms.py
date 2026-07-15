import datetime
from decimal import Decimal

from django.test import TestCase

from atelier.forms import ClientForm, RobeForm, TransactionForm
from atelier.models import Client, Robe


class ClientFormTests(TestCase):

    def test_valide_avec_champs_minimaux(self):
        form = ClientForm(data={'nom': 'Dupont', 'prenom': 'Claire'})
        self.assertTrue(form.is_valid(), form.errors)

    def test_date_naissance_accepte_le_format_jour_mois_annee(self):
        form = ClientForm(data={
            'nom': 'Dupont', 'prenom': 'Claire', 'date_naissance': '12/05/1990',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['date_naissance'], datetime.date(1990, 5, 12))

    def test_telephone_invalide_bloque_le_formulaire(self):
        form = ClientForm(data={
            'nom': 'Dupont', 'prenom': 'Claire', 'telephone': 'pas-un-numero',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('telephone', form.errors)

    def test_nom_manquant_bloque_le_formulaire(self):
        form = ClientForm(data={'prenom': 'Claire'})
        self.assertFalse(form.is_valid())
        self.assertIn('nom', form.errors)

    def test_classe_css_field_input_appliquee(self):
        form = ClientForm()
        self.assertIn('field-input', form.fields['nom'].widget.attrs.get('class', ''))
        self.assertIn('field-input', form.fields['date_naissance'].widget.attrs.get('class', ''))


class RobeFormTests(TestCase):

    def setUp(self):
        self.cliente = Client.objects.create(nom="Dupont", prenom="Claire")

    def _donnees_valides(self, **overrides):
        data = {
            'client': self.cliente.id,
            'nom_modele': 'Robe Sirène Ivoire',
            'date_commencement': '01/06/2026',
            'date_livraison': '20/07/2026',
            'cout_tissu': '120.00',
            'cout_main_doeuvre': '300.00',
            'prix_total': '650.00',
            'devise': 'ILS',
        }
        data.update(overrides)
        return data

    def test_valide_avec_toutes_les_donnees(self):
        form = RobeForm(data=self._donnees_valides())
        self.assertTrue(form.is_valid(), form.errors)

    def test_client_manquant_bloque_le_formulaire(self):
        data = self._donnees_valides()
        del data['client']
        form = RobeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('client', form.errors)

    def test_dates_au_mauvais_format_sont_rejetees(self):
        form = RobeForm(data=self._donnees_valides(date_commencement='2026-06-01'))
        self.assertFalse(form.is_valid())
        self.assertIn('date_commencement', form.errors)

    def test_devise_par_defaut_est_ils(self):
        form = RobeForm()
        self.assertEqual(form.fields['devise'].initial, 'ILS')

    def test_couts_initiaux_a_none_pour_une_nouvelle_robe(self):
        form = RobeForm()
        self.assertIsNone(form.initial.get('cout_tissu'))
        self.assertIsNone(form.initial.get('cout_main_doeuvre'))
        self.assertIsNone(form.initial.get('prix_total'))

    def test_couts_existants_conserves_lors_dune_modification(self):
        robe = Robe.objects.create(
            client=self.cliente, nom_modele="Robe existante",
            date_commencement=datetime.date(2026, 1, 1),
            date_livraison=datetime.date(2026, 2, 1),
            cout_tissu=Decimal("80.00"), cout_main_doeuvre=Decimal("150.00"),
            prix_total=Decimal("400.00"),
        )
        form = RobeForm(instance=robe)
        # Le prix existant ne doit pas être écrasé à None pour une modification
        self.assertEqual(form.initial.get('cout_tissu'), Decimal("80.00"))
        self.assertEqual(form.initial.get('prix_total'), Decimal("400.00"))


class TransactionFormTests(TestCase):

    def test_valide_avec_toutes_les_donnees(self):
        form = TransactionForm(data={
            'type': 'DEPENSE',
            'montant': '45.00',
            'categorie': 'MATERIEL',
            'designation': 'Entretien machine à coudre',
            'date': '10/07/2026',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_montant_manquant_bloque_le_formulaire(self):
        form = TransactionForm(data={
            'type': 'DEPENSE', 'categorie': 'MATERIEL',
            'designation': 'Entretien', 'date': '10/07/2026',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('montant', form.errors)

    def test_type_invalide_est_rejete(self):
        form = TransactionForm(data={
            'type': 'AUTRE_CHOSE', 'montant': '10.00', 'categorie': 'AUTRE',
            'designation': 'Test', 'date': '10/07/2026',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('type', form.errors)

    def test_champ_robe_absent_du_formulaire(self):
        # Le lien vers une robe est déduit automatiquement des finances,
        # il ne doit plus apparaître dans le formulaire rapide.
        form = TransactionForm()
        self.assertNotIn('robe', form.fields)
