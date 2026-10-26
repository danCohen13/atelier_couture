"""Protection de la vie privée : fiche d'information, suppression/anonymisation, dossiers inactifs, incidents."""
import datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from atelier.models import Atelier, Client, IncidentSecurite, Location, Paiement, Robe, RobeLocation
from atelier.services import confidentialite as vp
from atelier.tests.outils import atelier_test, utilisateur_test


def jour(offset=0):
    return datetime.date.today() + datetime.timedelta(days=offset)


class Base(TestCase):
    def setUp(self):
        utilisateur_test('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(atelier=atelier_test(), 
            nom='Dupont', prenom='Claire', telephone='+972501234567', email='c@example.com',
            date_naissance=datetime.date(1990, 1, 1), tour_taille=Decimal('70'),
            notes_morphologie='Épaules larges', information_remise_le=jour(-5))

    def robe(self, cliente=None, livraison=0):
        return Robe.objects.create(client=cliente or self.cliente, nom_modele='Robe A',
                                   date_commencement=jour(livraison - 20), date_livraison=jour(livraison),
                                   prix_total=Decimal('1000'))


class SuppressionEtAnonymisationTests(Base):
    def test_cliente_sans_historique_supprimee(self):
        r = self.client.post(reverse('supprimer_cliente', args=[self.cliente.pk]))
        self.assertRedirects(r, reverse('liste_clientes'))
        self.assertFalse(Client.objects.exists())

    def test_cliente_avec_historique_anonymisee_et_comptabilite_conservee(self):
        robe = self.robe()
        Paiement.objects.create(robe=robe, montant=Decimal('300'))
        self.client.post(reverse('supprimer_cliente', args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.est_anonymisee)
        self.assertEqual((self.cliente.nom, self.cliente.prenom), ('Cliente', 'anonymisée'))
        for champ in ('telephone', 'email', 'date_naissance', 'tour_taille', 'notes_morphologie',
                      'information_remise_le'):
            self.assertIsNone(getattr(self.cliente, champ), champ)
        robe.refresh_from_db()
        self.assertEqual(robe.prix_total, Decimal('1000'))
        self.assertEqual(robe.paiements.get().montant, Decimal('300'))

    def test_notes_de_location_effacees(self):
        stock = RobeLocation.objects.create(atelier=atelier_test(), reference_stock='L1', nom_modele='A', taille='38', couleur='x',
                                            prix_location_defaut=1, caution_defaut=1)
        loc = Location.objects.create(client=self.cliente, robe_location=stock, date_debut=jour(), date_fin_prevue=jour(2),
                                      prix_convenu=1, caution_montant=1, notes='Claire veut un ourlet', etat_avant='ok')
        vp.anonymiser_cliente(self.cliente)
        loc.refresh_from_db()
        self.assertEqual((loc.notes, loc.etat_avant), ('', ''))

    def test_suppression_est_post_only(self):
        url = reverse('supprimer_cliente', args=[self.cliente.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Client.objects.exists())

    def test_les_ecritures_comptables_restent_dans_les_finances(self):
        self.robe()
        self.client.post(reverse('supprimer_cliente', args=[self.cliente.pk]))
        ctx = self.client.get(reverse('finances')).context
        self.assertEqual(ctx['total_recettes'], Decimal('1000'))

    def test_fiche_affiche_le_statut_et_les_actions(self):
        page = self.client.get(reverse('fiche_cliente', args=[self.cliente.pk]))
        self.assertContains(page, "Fiche d'information remise le")
        self.assertContains(page, 'Effacer ses données')
        self.robe()
        self.client.post(reverse('supprimer_cliente', args=[self.cliente.pk]))
        page = self.client.get(reverse('fiche_cliente', args=[self.cliente.pk]))
        self.assertContains(page, 'Dossier anonymisé')
        self.assertNotContains(page, 'Effacer ses données')


class InformationRemiseTests(Base):
    def test_marquer_comme_remise(self):
        self.cliente.information_remise_le = None
        self.cliente.save()
        self.assertContains(self.client.get(reverse('fiche_cliente', args=[self.cliente.pk])), 'marquer comme remise')
        r = self.client.post(reverse('information_remise', args=[self.cliente.pk]))
        self.assertRedirects(r, reverse('fiche_cliente', args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.information_remise_le, timezone.localdate())

    def test_post_only_et_protege(self):
        url = reverse('information_remise', args=[self.cliente.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(reverse('supprimer_cliente', args=[self.cliente.pk])).status_code, 302)
        self.assertTrue(Client.objects.exists())

    def test_champ_date_dans_le_formulaire(self):
        r = self.client.post(reverse('modifier_client', args=[self.cliente.pk]), {
            'nom': 'Dupont', 'prenom': 'Claire', 'information_remise_le': '01/10/2026'})
        self.assertEqual(r.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.information_remise_le, datetime.date(2026, 10, 1))

    def test_avertissement_sur_les_notes_medicales(self):
        page = self.client.get(reverse('ajouter_client'))
        self.assertContains(page, "pas d&#x27;information médicale")
        self.assertContains(page, 'ne prononce ni nom')


class InactivesTests(Base):
    def test_dossier_recent_pas_inactif(self):
        Client.objects.filter(pk=self.cliente.pk).update(cree_le=timezone.now())
        self.assertEqual(vp.clientes_inactives(atelier_test(), 3), [])

    def test_dossier_ancien_sans_activite(self):
        Client.objects.filter(pk=self.cliente.pk).update(cree_le=timezone.now() - datetime.timedelta(days=5 * 365))
        ((cliente, derniere),) = vp.clientes_inactives(atelier_test(), 3)
        self.assertEqual(cliente.pk, self.cliente.pk)

    def test_activite_recente_ecarte_le_dossier(self):
        Client.objects.filter(pk=self.cliente.pk).update(cree_le=timezone.now() - datetime.timedelta(days=5 * 365))
        robe = self.robe(livraison=-30)
        self.assertEqual(vp.clientes_inactives(atelier_test(), 3), [])
        robe.date_livraison = jour(-4 * 365)
        robe.save()
        self.assertEqual(len(vp.clientes_inactives(atelier_test(), 3)), 1)
        Paiement.objects.create(robe=robe, montant=Decimal('10'), date=jour(-10))
        self.assertEqual(vp.clientes_inactives(atelier_test(), 3), [])

    def test_anonymisees_exclues_et_ancien_dossier_sans_date_de_creation(self):
        Client.objects.filter(pk=self.cliente.pk).update(cree_le=None)
        self.assertEqual(len(vp.clientes_inactives(atelier_test(), 3)), 1)   # dossier historique sans aucune trace
        self.robe(livraison=-2000)
        vp.anonymiser_cliente(self.cliente)
        self.assertEqual(vp.clientes_inactives(atelier_test(), 3), [])

    def test_page_hub(self):
        Client.objects.filter(pk=self.cliente.pk).update(cree_le=timezone.now() - datetime.timedelta(days=5 * 365))
        page = self.client.get(reverse('confidentialite'), {'annees': '3'})
        self.assertContains(page, 'DUPONT Claire')
        self.assertContains(page, 'Coordonnées à renseigner')

    def test_hub_sans_alerte_quand_le_contact_est_renseigne(self):
        Atelier.objects.filter(pk=atelier_test().pk).update(contact_confidentialite='contact@atelier.example')
        self.assertNotContains(self.client.get(reverse('confidentialite')), 'Coordonnées à renseigner')

    def test_parametre_annees_borne(self):
        self.assertEqual(self.client.get(reverse('confidentialite'), {'annees': 'abc'}).status_code, 200)
        self.assertEqual(self.client.get(reverse('confidentialite'), {'annees': '999'}).context['annees'], 20)
        self.assertEqual(self.client.get(reverse('confidentialite'), {'annees': '-4'}).context['annees'], 1)

    def test_compte_des_dossiers_sans_fiche(self):
        Client.objects.create(atelier=atelier_test(), nom='X', prenom='Y')
        self.assertEqual(self.client.get(reverse('confidentialite')).context['sans_information'], 1)


class FicheEtIncidentsTests(Base):
    @override_settings(CONTACT_CONFIDENTIALITE='contact@atelier.example')
    def test_fiche_pdf(self):
        r = self.client.get(reverse('confidentialite_fiche_pdf'))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_pages_protegees(self):
        self.client.logout()
        for nom in ('confidentialite', 'confidentialite_fiche_pdf'):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 302, nom)

    def test_lien_dans_la_barre_laterale_sans_activer_le_tableau_de_bord(self):
        page = self.client.get(reverse('confidentialite')).content.decode()
        self.assertIn(reverse('confidentialite'), page)
        self.assertEqual(page.count('sidebar-link is-active'), 1)

    def test_registre_des_incidents(self):
        incident = IncidentSecurite.objects.create(atelier=atelier_test(), description='Téléphone perdu', grave=False)
        self.assertEqual(IncidentSecurite.objects.get(), incident)
        self.assertIn('Téléphone perdu', str(incident))

    def test_admin_enregistre_le_registre(self):
        from django.contrib import admin
        self.assertIn(IncidentSecurite, admin.site._registry)

    def test_document_de_reference_present(self):
        import pathlib
        doc = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'PROTECTION_DES_DONNEES.md'
        texte = doc.read_text(encoding='utf-8')
        for mot in ('Prestataires', 'Durées de conservation', 'Incident de sécurité', 'Revue annuelle'):
            self.assertIn(mot, texte)
