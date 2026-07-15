import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from atelier.models import Client, Robe, Tache, Transaction


class ClientModelTests(TestCase):

    def test_str_representation_uppercases_nom(self):
        client = Client.objects.create(nom="dupont", prenom="Claire")
        self.assertEqual(str(client), "DUPONT Claire")

    def test_telephone_accepts_international_format(self):
        client = Client(nom="Martin", prenom="Sophie", telephone="+33612345678")
        client.full_clean()  # ne doit pas lever

    def test_telephone_rejects_invalid_format(self):
        client = Client(nom="Martin", prenom="Sophie", telephone="0612345678-invalide")
        with self.assertRaises(ValidationError):
            client.full_clean()

    def test_telephone_and_email_are_optional(self):
        client = Client(nom="Martin", prenom="Sophie")
        client.full_clean()  # ne doit pas lever malgré l'absence de coordonnées


class RobeModelTests(TestCase):

    def setUp(self):
        self.client_ = Client.objects.create(nom="Dupont", prenom="Claire")

    def _creer_robe(self, **kwargs):
        defaults = dict(
            client=self.client_,
            nom_modele="Robe Sirène Ivoire",
            date_commencement=datetime.date.today(),
            date_livraison=datetime.date.today() + datetime.timedelta(days=10),
            cout_tissu=Decimal("120.00"),
            cout_main_doeuvre=Decimal("300.00"),
            prix_total=Decimal("650.00"),
        )
        defaults.update(kwargs)
        return Robe.objects.create(**defaults)

    def test_str_representation(self):
        robe = self._creer_robe()
        self.assertIn("Robe Sirène Ivoire", str(robe))
        self.assertIn("Dupont", str(robe))

    def test_symbole_devise_ils_par_defaut(self):
        robe = self._creer_robe()
        self.assertEqual(robe.devise, 'ILS')
        self.assertEqual(robe.symbole_devise, '₪')

    def test_symbole_devise_eur(self):
        robe = self._creer_robe(devise='EUR')
        self.assertEqual(robe.symbole_devise, '€')

    def test_symbole_devise_usd(self):
        robe = self._creer_robe(devise='USD')
        self.assertEqual(robe.symbole_devise, '$')

    def test_jours_restants_futur_est_positif(self):
        robe = self._creer_robe(date_livraison=datetime.date.today() + datetime.timedelta(days=5))
        self.assertEqual(robe.jours_restants, 5)

    def test_jours_restants_passe_est_negatif(self):
        robe = self._creer_robe(date_livraison=datetime.date.today() - datetime.timedelta(days=3))
        self.assertEqual(robe.jours_restants, -3)

    def test_progression_sans_taches_est_zero(self):
        robe = self._creer_robe()
        self.assertEqual(robe.progression, 0)

    def test_progression_partielle(self):
        robe = self._creer_robe()
        Tache.objects.create(robe=robe, libelle="Toile d'essai", est_faite=True)
        Tache.objects.create(robe=robe, libelle="Coupe du tissu", est_faite=True)
        Tache.objects.create(robe=robe, libelle="Assemblage", est_faite=False)
        Tache.objects.create(robe=robe, libelle="Finitions", est_faite=False)
        self.assertEqual(robe.progression, 50)

    def test_progression_complete(self):
        robe = self._creer_robe()
        Tache.objects.create(robe=robe, libelle="Toile d'essai", est_faite=True)
        Tache.objects.create(robe=robe, libelle="Coupe du tissu", est_faite=True)
        self.assertEqual(robe.progression, 100)


class TacheModelTests(TestCase):

    def setUp(self):
        client = Client.objects.create(nom="Dupont", prenom="Claire")
        self.robe = Robe.objects.create(
            client=client, nom_modele="Robe Test",
            date_commencement=datetime.date.today(),
            date_livraison=datetime.date.today(),
        )

    def test_str_quand_faite(self):
        tache = Tache.objects.create(robe=self.robe, libelle="Ourlet", est_faite=True)
        self.assertIn("Fait", str(tache))

    def test_str_quand_a_faire(self):
        tache = Tache.objects.create(robe=self.robe, libelle="Ourlet", est_faite=False)
        self.assertIn("À faire", str(tache))


class TransactionModelTests(TestCase):

    def setUp(self):
        client = Client.objects.create(nom="Dupont", prenom="Claire")
        self.robe = Robe.objects.create(
            client=client, nom_modele="Robe Test",
            date_commencement=datetime.date.today(),
            date_livraison=datetime.date.today(),
        )

    def test_str_representation(self):
        t = Transaction.objects.create(
            type='DEPENSE', montant=Decimal("45.00"), categorie='MATERIEL',
            designation="Entretien machine", date=datetime.date.today(),
        )
        self.assertIn("Entretien machine", str(t))
        self.assertIn("45.00", str(t))

    def test_ordering_plus_recent_en_premier(self):
        ancienne = Transaction.objects.create(
            type='DEPENSE', montant=Decimal("10.00"), categorie='AUTRE',
            designation="Ancienne", date=datetime.date.today() - datetime.timedelta(days=5),
        )
        recente = Transaction.objects.create(
            type='DEPENSE', montant=Decimal("10.00"), categorie='AUTRE',
            designation="Récente", date=datetime.date.today(),
        )
        transactions = list(Transaction.objects.all())
        self.assertEqual(transactions[0], recente)
        self.assertEqual(transactions[1], ancienne)

    def test_robe_devient_null_si_robe_supprimee(self):
        transaction = Transaction.objects.create(
            type='RECETTE', montant=Decimal("100.00"), categorie='PAIEMENT_CLIENT',
            designation="Acompte", date=datetime.date.today(), robe=self.robe,
        )
        self.robe.delete()
        transaction.refresh_from_db()
        self.assertIsNone(transaction.robe)
        # La trace financière doit survivre à la suppression de la robe
        self.assertTrue(Transaction.objects.filter(pk=transaction.pk).exists())
