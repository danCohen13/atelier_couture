import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from atelier.models import Client, Robe, Tache


class AuthRequiredTests(TestCase):
    """Toutes les pages de l'atelier doivent exiger une connexion."""

    def setUp(self):
        self.cliente = Client.objects.create(nom="Dupont", prenom="Claire")
        self.robe = Robe.objects.create(
            client=self.cliente, nom_modele="Robe Test",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
        )

    def _assert_redirects_to_login(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_protege(self):
        self._assert_redirects_to_login(reverse('dashboard'))

    def test_ajouter_client_protege(self):
        self._assert_redirects_to_login(reverse('ajouter_client'))

    def test_ajouter_robe_protege(self):
        self._assert_redirects_to_login(reverse('ajouter_robe'))

    def test_liste_clientes_protege(self):
        self._assert_redirects_to_login(reverse('liste_clientes'))

    def test_fiche_cliente_protegee(self):
        self._assert_redirects_to_login(reverse('fiche_cliente', args=[self.cliente.id]))

    def test_modifier_client_protege(self):
        self._assert_redirects_to_login(reverse('modifier_client', args=[self.cliente.id]))

    def test_modifier_robe_protege(self):
        self._assert_redirects_to_login(reverse('modifier_robe', args=[self.robe.id]))


class DashboardViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(nom="Dupont", prenom="Claire")

        self.robe_en_cours = Robe.objects.create(
            client=self.cliente, nom_modele="Robe Alpha",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
            prix_total=Decimal("500.00"),
        )
        Tache.objects.create(robe=self.robe_en_cours, libelle="Toile", est_faite=False)

        self.robe_terminee = Robe.objects.create(
            client=self.cliente, nom_modele="Robe Beta",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
            prix_total=Decimal("900.00"),
        )
        Tache.objects.create(robe=self.robe_terminee, libelle="Toile", est_faite=True)

    def test_filtre_actifs_exclut_les_robes_terminees(self):
        response = self.client.get(reverse('dashboard'), {'status': 'actifs'})
        robes = response.context['robes']
        self.assertIn(self.robe_en_cours, robes)
        self.assertNotIn(self.robe_terminee, robes)

    def test_filtre_termines_ninclut_que_les_robes_terminees(self):
        response = self.client.get(reverse('dashboard'), {'status': 'termines'})
        robes = response.context['robes']
        self.assertIn(self.robe_terminee, robes)
        self.assertNotIn(self.robe_en_cours, robes)

    def test_filtre_toutes_inclut_tout(self):
        response = self.client.get(reverse('dashboard'), {'status': 'toutes'})
        robes = response.context['robes']
        self.assertIn(self.robe_en_cours, robes)
        self.assertIn(self.robe_terminee, robes)

    def test_tri_par_prix_decroissant(self):
        response = self.client.get(reverse('dashboard'), {'status': 'toutes', 'tri': 'prix'})
        robes = response.context['robes']
        self.assertEqual(robes[0], self.robe_terminee)  # 900 > 500

    def test_tri_par_modele_alphabetique(self):
        response = self.client.get(reverse('dashboard'), {'status': 'toutes', 'tri': 'modele'})
        robes = response.context['robes']
        self.assertEqual(robes[0].nom_modele, "Robe Alpha")


class ClientCrudTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')

    def test_ajouter_client_valide_cree_et_redirige(self):
        response = self.client.post(reverse('ajouter_client'), {
            'nom': 'Martin', 'prenom': 'Sophie',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(Client.objects.filter(nom='Martin', prenom='Sophie').exists())

    def test_ajouter_client_invalide_reaffiche_le_formulaire(self):
        response = self.client.post(reverse('ajouter_client'), {'prenom': 'Sophie'})  # nom manquant
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Client.objects.filter(prenom='Sophie').exists())

    def test_modifier_client_met_a_jour(self):
        cliente = Client.objects.create(nom="Dupont", prenom="Claire")
        response = self.client.post(reverse('modifier_client', args=[cliente.id]), {
            'nom': 'Dupont', 'prenom': 'Claire', 'telephone': '+33612345678',
        })
        self.assertRedirects(response, reverse('fiche_cliente', args=[cliente.id]))
        cliente.refresh_from_db()
        self.assertEqual(cliente.telephone, '+33612345678')

    def test_recherche_par_nom(self):
        Client.objects.create(nom="Dupont", prenom="Claire")
        Client.objects.create(nom="Martin", prenom="Sophie")
        response = self.client.get(reverse('liste_clientes'), {'q': 'dupont'})
        clientes = response.context['clientes']
        self.assertEqual(list(clientes), list(Client.objects.filter(nom='Dupont')))

    def test_recherche_par_prenom(self):
        Client.objects.create(nom="Dupont", prenom="Claire")
        Client.objects.create(nom="Martin", prenom="Sophie")
        response = self.client.get(reverse('liste_clientes'), {'q': 'sophie'})
        clientes = response.context['clientes']
        self.assertEqual(clientes.count(), 1)
        self.assertEqual(clientes.first().prenom, 'Sophie')

    def test_fiche_cliente_ne_montre_que_ses_propres_robes(self):
        cliente_a = Client.objects.create(nom="Dupont", prenom="Claire")
        cliente_b = Client.objects.create(nom="Martin", prenom="Sophie")
        robe_a = Robe.objects.create(
            client=cliente_a, nom_modele="Robe A",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
        )
        Robe.objects.create(
            client=cliente_b, nom_modele="Robe B",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
        )
        response = self.client.get(reverse('fiche_cliente', args=[cliente_a.id]))
        robes = response.context['robes']
        self.assertEqual(list(robes), [robe_a])


class RobeCrudTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(nom="Dupont", prenom="Claire")

    def test_ajouter_robe_valide_cree_et_redirige(self):
        response = self.client.post(reverse('ajouter_robe'), {
            'client': self.cliente.id,
            'nom_modele': 'Robe Sirène',
            'date_commencement': '01/06/2026',
            'date_livraison': '20/07/2026',
            'cout_tissu': '120.00',
            'cout_main_doeuvre': '300.00',
            'prix_total': '650.00',
            'devise': 'ILS',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(Robe.objects.filter(nom_modele='Robe Sirène').exists())

    def test_modifier_robe_met_a_jour_les_couts(self):
        robe = Robe.objects.create(
            client=self.cliente, nom_modele="Robe Test",
            date_commencement=datetime.date(2026, 1, 1), date_livraison=datetime.date(2026, 2, 1),
            cout_tissu=Decimal("100.00"), cout_main_doeuvre=Decimal("200.00"), prix_total=Decimal("400.00"),
        )
        response = self.client.post(reverse('modifier_robe', args=[robe.id]), {
            'client': self.cliente.id,
            'nom_modele': 'Robe Test',
            'date_commencement': '01/01/2026',
            'date_livraison': '01/02/2026',
            'cout_tissu': '150.00',
            'cout_main_doeuvre': '200.00',
            'prix_total': '450.00',
            'devise': 'ILS',
        })
        self.assertEqual(response.status_code, 302)
        robe.refresh_from_db()
        self.assertEqual(robe.cout_tissu, Decimal("150.00"))
        self.assertEqual(robe.prix_total, Decimal("450.00"))

    def test_supprimer_robe_la_retire_de_la_base(self):
        robe = Robe.objects.create(
            client=self.cliente, nom_modele="Robe à supprimer",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
        )
        response = self.client.get(reverse('supprimer_robe', args=[robe.id]))
        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(Robe.objects.filter(pk=robe.id).exists())


class TacheTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        cliente = Client.objects.create(nom="Dupont", prenom="Claire")
        self.robe = Robe.objects.create(
            client=cliente, nom_modele="Robe Test",
            date_commencement=datetime.date.today(), date_livraison=datetime.date.today(),
        )

    def test_ajout_rapide_type_connu_cree_la_tache(self):
        self.client.get(reverse('ajouter_tache_rapide', args=[self.robe.id, 'toile']))
        self.assertTrue(self.robe.taches.filter(libelle="Toile d'essai").exists())

    def test_ajout_rapide_type_inconnu_ne_cree_rien(self):
        self.client.get(reverse('ajouter_tache_rapide', args=[self.robe.id, 'inexistant']))
        self.assertEqual(self.robe.taches.count(), 0)

    def test_tache_personnalisee_avec_libelle_est_creee(self):
        self.client.post(reverse('ajouter_tache_personnalisee', args=[self.robe.id]), {
            'libelle': 'Poser la fermeture éclair',
        })
        self.assertTrue(self.robe.taches.filter(libelle='Poser la fermeture éclair').exists())

    def test_tache_personnalisee_vide_est_ignoree(self):
        self.client.post(reverse('ajouter_tache_personnalisee', args=[self.robe.id]), {
            'libelle': '   ',
        })
        self.assertEqual(self.robe.taches.count(), 0)

    def test_toggle_tache_inverse_le_statut(self):
        tache = Tache.objects.create(robe=self.robe, libelle="Ourlet", est_faite=False)
        self.client.get(reverse('toggle_tache', args=[tache.id]))
        tache.refresh_from_db()
        self.assertTrue(tache.est_faite)
        self.client.get(reverse('toggle_tache', args=[tache.id]))
        tache.refresh_from_db()
        self.assertFalse(tache.est_faite)

    def test_supprimer_tache_la_retire(self):
        tache = Tache.objects.create(robe=self.robe, libelle="Ourlet", est_faite=False)
        self.client.get(reverse('supprimer_tache', args=[tache.id]))
        self.assertFalse(Tache.objects.filter(pk=tache.id).exists())
