import datetime
import io
import tempfile
import zipfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from atelier.models import Adhesion, Atelier, Client
from atelier.services import sauvegarde as svc
from atelier.tests.outils import atelier_test, utilisateur_test

CLE = svc.generer_cle()


@override_settings(BACKUP_ENCRYPTION_KEY=CLE)
class SauvegardeTests(TestCase):
    def setUp(self):
        self.atelier = atelier_test()
        utilisateur_test('proprio', password='x-motdepasse-123')
        Client.objects.create(atelier=self.atelier, nom='Cohen', prenom='Sarah', telephone='+972501234567')

    def test_le_fichier_est_chiffre(self):
        contenu = svc.exporter_chiffre()
        self.assertNotIn(b'Sarah', contenu)
        self.assertNotIn(b'Cohen', contenu)
        self.assertIn('Sarah', svc.dechiffrer(contenu))

    def test_refus_sans_cle(self):
        with override_settings(BACKUP_ENCRYPTION_KEY=''):
            with self.assertRaises(svc.ErreurSauvegarde):
                svc.exporter_chiffre()

    def test_mauvaise_cle_refusee(self):
        contenu = svc.exporter_chiffre()
        with override_settings(BACKUP_ENCRYPTION_KEY=svc.generer_cle()):
            with self.assertRaises(svc.ErreurSauvegarde):
                svc.dechiffrer(contenu)

    def test_donnees_sensibles_ou_inutiles_exclues(self):
        modeles = svc.compter(svc.dechiffrer(svc.exporter_chiffre()))
        self.assertIn('atelier.client', modeles)
        self.assertNotIn('sessions.session', modeles)
        self.assertNotIn('atelier.codereinitialisation', modeles)

    def test_commande_sauvegarde_puis_verification(self):
        with tempfile.TemporaryDirectory() as dossier:
            call_command('sauvegarde', dossier=dossier, stdout=io.StringIO())
            sortie = io.StringIO()
            call_command('verifier_sauvegarde', dossier=dossier, stdout=sortie)
            self.assertIn('lisible', sortie.getvalue())

    def test_verification_echoue_sans_sauvegarde(self):
        with tempfile.TemporaryDirectory() as dossier:
            with self.assertRaises(CommandError):
                call_command('verifier_sauvegarde', dossier=dossier)

    def test_verification_echoue_si_trop_ancienne(self):
        with tempfile.TemporaryDirectory() as dossier:
            depot = svc.StockageLocal(dossier)
            vieux = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
            depot.deposer(svc.nom_fichier(vieux), svc.exporter_chiffre())
            with self.assertRaisesMessage(CommandError, 'trop ancienne'):
                call_command('verifier_sauvegarde', dossier=dossier)

    def test_restauration_dans_une_base_vide(self):
        with tempfile.TemporaryDirectory() as dossier:
            call_command('sauvegarde', dossier=dossier, stdout=io.StringIO())
            # Base vivante : la restauration est refusée.
            with self.assertRaisesMessage(CommandError, "pas vide"):
                call_command('restaurer_sauvegarde', dossier=dossier, confirmer=True)
            # Catastrophe : tout disparaît, puis on restaure.
            Client.objects.all().delete()
            Adhesion.objects.all().delete()
            User.objects.all().delete()
            Atelier.objects.all().delete()
            with self.assertRaisesMessage(CommandError, '--confirmer'):
                call_command('restaurer_sauvegarde', dossier=dossier)
            call_command('restaurer_sauvegarde', dossier=dossier, confirmer=True, stdout=io.StringIO())
        self.assertEqual(Client.objects.get().prenom, 'Sarah')
        self.assertTrue(User.objects.filter(username='proprio').exists())
        self.assertTrue(Adhesion.objects.get().atelier.nom)

    def test_depot_s3_utilise_le_bucket_et_le_prefixe(self):
        faux = mock.Mock()
        faux.list_objects_v2.return_value = {'Contents': []}
        with override_settings(BACKUP_S3_BUCKET='b', BACKUP_S3_ACCESS_KEY='a', BACKUP_S3_SECRET_KEY='s',
                               BACKUP_S3_ENDPOINT='https://exemple.invalid', BACKUP_PREFIX='sauvegardes/'):
            with mock.patch('boto3.client', return_value=faux):
                nom, octets, _ = svc.sauvegarder(svc.stockage())
        args = faux.put_object.call_args.kwargs
        self.assertEqual(args['Bucket'], 'b')
        self.assertEqual(args['Key'], 'sauvegardes/' + nom)
        self.assertEqual(len(args['Body']), octets)


class RotationTests(TestCase):
    def test_politique_de_conservation(self):
        maintenant = datetime.datetime(2026, 10, 27, 1, 0, tzinfo=datetime.timezone.utc)
        jours = [maintenant - datetime.timedelta(days=n) for n in range(0, 120)]
        noms = [svc.nom_fichier(j) for j in jours]
        supprimes = set(svc.a_supprimer(noms, maintenant))
        gardes = [n for n in noms if n not in supprimes]
        # Tout ce qui a moins de 14 jours est conservé…
        for j in jours[:14]:
            self.assertIn(svc.nom_fichier(j), gardes)
        # …les plus anciennes disparaissent, sauf la 1re de chaque mois.
        self.assertLess(len(gardes), 30)
        self.assertIn(svc.nom_fichier(datetime.datetime(2026, 7, 1, 1, 0, tzinfo=datetime.timezone.utc)), gardes)
        self.assertNotIn(svc.nom_fichier(datetime.datetime(2026, 7, 2, 1, 0, tzinfo=datetime.timezone.utc)), gardes)

    def test_fichiers_etrangers_ignores(self):
        self.assertEqual(svc.a_supprimer(['notes.txt', 'autre.json']), [])


class ExportAtelierTests(TestCase):
    def setUp(self):
        self.a = Atelier.objects.create(nom='Atelier A')
        self.b = Atelier.objects.create(nom='Atelier B')
        self.user = utilisateur_test('a', password='x-motdepasse-123', atelier=self.a)
        Client.objects.create(atelier=self.a, nom='Levi', prenom='Dana')
        Client.objects.create(atelier=self.b, nom='Secret', prenom='Autre')

    def telecharger(self):
        self.client.login(username='a', password='x-motdepasse-123')
        return self.client.get(reverse('exporter_donnees'))

    def test_zip_contient_seulement_les_donnees_de_l_atelier(self):
        reponse = self.telecharger()
        self.assertEqual(reponse.status_code, 200)
        archive = zipfile.ZipFile(io.BytesIO(reponse.content))
        self.assertIn('clientes.csv', archive.namelist())
        texte = ''.join(archive.read(n).decode('utf-8') for n in archive.namelist())
        self.assertIn('Dana', texte)
        self.assertNotIn('Secret', texte)
        self.assertNotIn('Autre', texte)

    def test_employee_refusee(self):
        Adhesion.objects.filter(user=self.user).update(role='EMPLOYE')
        self.assertEqual(self.telecharger().status_code, 403)

    def test_connexion_requise(self):
        self.assertEqual(self.client.get(reverse('exporter_donnees')).status_code, 302)
