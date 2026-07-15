import datetime
import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from atelier.models import Client, Robe, Transaction


class FinancesAuthTests(TestCase):

    def test_finances_protegee(self):
        response = self.client.get(reverse('finances'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_ajouter_transaction_protegee(self):
        response = self.client.get(reverse('ajouter_transaction'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class FinancesAutoLignesTests(TestCase):
    """Les coûts d'une robe doivent apparaître dans les finances sans ressaisie."""

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(nom="Dupont", prenom="Claire")

    def test_couts_de_robe_generent_des_totaux_sans_transaction_manuelle(self):
        Robe.objects.create(
            client=self.cliente, nom_modele="Robe Sirène",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
            cout_tissu=Decimal("120.00"), cout_main_doeuvre=Decimal("300.00"),
            prix_total=Decimal("650.00"),
        )
        self.assertEqual(Transaction.objects.count(), 0)  # aucune saisie manuelle

        response = self.client.get(reverse('finances'), {'periode': 'tout'})
        self.assertEqual(response.context['total_recettes'], Decimal("650.00"))
        # Seul le tissu est une vraie dépense : la main d'œuvre est une
        # composante du prix facturé, pas une sortie d'argent séparée.
        self.assertEqual(response.context['total_depenses'], Decimal("120.00"))
        self.assertEqual(response.context['benefice_net'], Decimal("530.00"))

    def test_main_doeuvre_nest_pas_comptee_comme_depense(self):
        Robe.objects.create(
            client=self.cliente, nom_modele="Robe Sans Tissu Facture",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
            cout_main_doeuvre=Decimal("300.00"), prix_total=Decimal("650.00"),
        )
        response = self.client.get(reverse('finances'), {'periode': 'tout'})
        # Sans cout_tissu, aucune dépense ne doit être générée du tout
        self.assertEqual(response.context['total_depenses'], 0)

    def test_robe_sans_couts_ne_genere_pas_de_ligne(self):
        Robe.objects.create(
            client=self.cliente, nom_modele="Robe Sans Prix",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
        )
        response = self.client.get(reverse('finances'), {'periode': 'tout'})
        self.assertEqual(response.context['total_recettes'], 0)
        self.assertEqual(response.context['total_depenses'], 0)

    def test_transaction_manuelle_sajoute_aux_totaux_automatiques(self):
        Robe.objects.create(
            client=self.cliente, nom_modele="Robe Sirène",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
            cout_tissu=Decimal("100.00"), prix_total=Decimal("300.00"),
        )
        Transaction.objects.create(
            type='DEPENSE', montant=Decimal("50.00"), categorie='MATERIEL',
            designation="Entretien machine", date=datetime.date.today(),
        )
        response = self.client.get(reverse('finances'), {'periode': 'tout'})
        self.assertEqual(response.context['total_depenses'], Decimal("150.00"))  # 100 + 50


class FinancesPeriodeTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        aujourdhui = datetime.date.today()
        Transaction.objects.create(
            type='RECETTE', montant=Decimal("100.00"), categorie='PAIEMENT_CLIENT',
            designation="Aujourd'hui", date=aujourdhui,
        )
        Transaction.objects.create(
            type='RECETTE', montant=Decimal("200.00"), categorie='PAIEMENT_CLIENT',
            designation="Il y a 2 ans", date=aujourdhui.replace(year=aujourdhui.year - 2),
        )

    def test_periode_jour_nisole_que_les_operations_du_jour(self):
        response = self.client.get(reverse('finances'), {'periode': 'jour'})
        self.assertEqual(response.context['total_recettes'], Decimal("100.00"))

    def test_periode_annee_exclut_les_annees_precedentes(self):
        response = self.client.get(reverse('finances'), {'periode': 'annee'})
        self.assertEqual(response.context['total_recettes'], Decimal("100.00"))

    def test_periode_tout_inclut_tout_lhistorique(self):
        response = self.client.get(reverse('finances'), {'periode': 'tout'})
        self.assertEqual(response.context['total_recettes'], Decimal("300.00"))

    def test_periode_par_defaut_est_tout(self):
        response = self.client.get(reverse('finances'))
        self.assertEqual(response.context['periode'], 'tout')
        self.assertEqual(response.context['total_recettes'], Decimal("300.00"))


class FinancesGroupementMensuelTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')

    def test_les_lignes_sont_regroupees_par_mois(self):
        Transaction.objects.create(
            type='RECETTE', montant=Decimal("100.00"), categorie='PAIEMENT_CLIENT',
            designation="Juin", date=datetime.date(2026, 6, 15),
        )
        Transaction.objects.create(
            type='RECETTE', montant=Decimal("200.00"), categorie='PAIEMENT_CLIENT',
            designation="Juillet", date=datetime.date(2026, 7, 5),
        )
        response = self.client.get(reverse('finances'), {'periode': 'tout'})
        groupes = response.context['groupes']
        labels = [g['label'] for g in groupes]
        # Le mois le plus récent doit apparaître en premier
        self.assertEqual(labels[0], "Juillet 2026")
        self.assertEqual(labels[1], "Juin 2026")


class AjouterTransactionTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')

    def test_creation_valide_redirige_vers_finances(self):
        response = self.client.post(reverse('ajouter_transaction'), {
            'type': 'DEPENSE',
            'montant': '45.00',
            'categorie': 'MATERIEL',
            'designation': 'Entretien machine à coudre',
            'date': '10/07/2026',
        })
        self.assertRedirects(response, reverse('finances'))
        self.assertTrue(Transaction.objects.filter(designation='Entretien machine à coudre').exists())

    def test_creation_invalide_reaffiche_le_formulaire(self):
        response = self.client.post(reverse('ajouter_transaction'), {
            'type': 'DEPENSE', 'categorie': 'MATERIEL', 'date': '10/07/2026',
        })  # montant et designation manquants
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)


class FinancesChartDataTests(TestCase):
    """Le graphe recettes/dépenses doit recevoir des séries semaine/mois/année."""

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        cliente = Client.objects.create(nom="Dupont", prenom="Claire")
        Robe.objects.create(
            client=cliente, nom_modele="Robe Sirène",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
            cout_tissu=Decimal("100.00"), prix_total=Decimal("300.00"),
        )

    def test_chart_data_present_dans_le_contexte(self):
        response = self.client.get(reverse('finances'))
        self.assertIn('chart_data', response.context)

    def test_chart_data_contient_les_trois_granularites(self):
        response = self.client.get(reverse('finances'))
        chart_data = response.context['chart_data']
        self.assertIn('semaine', chart_data)
        self.assertIn('mois', chart_data)
        self.assertIn('annee', chart_data)

    def test_chart_data_series_coherentes(self):
        response = self.client.get(reverse('finances'))
        for granularite in ('semaine', 'mois', 'annee'):
            serie = response.context['chart_data'][granularite]
            self.assertEqual(len(serie['labels']), len(serie['recettes']))
            self.assertEqual(len(serie['labels']), len(serie['depenses']))

    def test_chart_data_est_serialisable_en_json_dans_le_gabarit(self):
        response = self.client.get(reverse('finances'))
        contenu = response.content.decode()
        self.assertIn('id="chart-data"', contenu)
        import re
        match = re.search(r'<script id="chart-data" type="application/json">(.*?)</script>', contenu, re.S)
        self.assertIsNotNone(match, "Le bloc JSON du graphe est absent du HTML rendu")
        donnees = json.loads(match.group(1))
        self.assertIn('mois', donnees)
