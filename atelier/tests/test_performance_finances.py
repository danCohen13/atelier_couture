"""Performance de la page Finances : pagination, chargement partagé, génération groupée."""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from atelier.models import Client, DepenseRecurrente, Transaction
from atelier.services.comptabilite import ecritures
from atelier.services.comptabilite.tableau import LIGNES_PAR_PAGE


class PerformanceFinancesTests(TestCase):
    def setUp(self):
        User.objects.create_user('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        Client.objects.create(nom='Dupont', prenom='Claire')
        aujourdhui = datetime.date.today()
        Transaction.objects.bulk_create([
            Transaction(type='DEPENSE', categorie='AUTRE', montant=Decimal('10'),
                        date=aujourdhui - datetime.timedelta(days=i % 300), designation=f'op {i}')
            for i in range(LIGNES_PAR_PAGE * 2 + 5)
        ])

    def get(self, **params):
        return self.client.get(reverse('finances'), {'periode': 'tout', **params})

    def test_premiere_page_limitee(self):
        reponse = self.get()
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context['pagination'].paginator.count, LIGNES_PAR_PAGE * 2 + 5)
        self.assertEqual(len(reponse.context['pagination'].object_list), LIGNES_PAR_PAGE)

    def test_derniere_page_et_page_invalide(self):
        derniere = self.get(page=3)
        self.assertEqual(len(derniere.context['pagination'].object_list), 5)
        self.assertEqual(self.get(page='abc').status_code, 200)
        self.assertEqual(self.get(page=999).context['pagination'].number, 3)

    def test_nombre_de_requetes_stable(self):
        with CaptureQueriesContext(connection) as ctx:
            self.get()
        self.assertLess(len(ctx), 25)

    def test_depenses_recurrentes_groupees_et_idempotentes(self):
        DepenseRecurrente.objects.create(
            designation='Loyer', categorie='AUTRE', montant=Decimal('100'),
            jour_du_mois=1, date_debut=datetime.date.today() - datetime.timedelta(days=100), actif=True)
        premiere = ecritures.generer_depenses_recurrentes()
        self.assertGreater(premiere, 0)
        self.assertEqual(ecritures.generer_depenses_recurrentes(), 0)
