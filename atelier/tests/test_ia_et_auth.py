import datetime
import json
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from atelier.models import Client, CodeReinitialisation, Robe, Tache, Transaction
from atelier.services.gemini import ErreurIA
from atelier.tests.outils import atelier_test, utilisateur_test


class ConnecteTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = utilisateur_test("couturiere", "c@example.com", "Password123!")

    def setUp(self):
        self.client.login(username="couturiere", password="Password123!")


class SaisieRapideIATests(ConnecteTestCase):
    url = property(lambda self: reverse("ajouter_transaction"))

    @mock.patch("atelier.views_finances.extraire_operation")
    def test_analyser_prerempli_le_formulaire_sans_rien_enregistrer(self, extraire):
        extraire.return_value = {"date": datetime.date(2026, 10, 5), "type": "DEPENSE", "categorie": "FOURNITURES",
                                 "designation": "Fil de soie", "montant": 45.5}
        reponse = self.client.post(self.url, {"texte_ia": "fil de soie 45,5", "analyser": ""})
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'value="05/10/2026"')          # date au format jj/mm/aaaa
        self.assertContains(reponse, 'value="Fil de soie"')
        self.assertContains(reponse, 'value="fil de soie 45,5"')    # la phrase reste affichée
        self.assertEqual(Transaction.objects.count(), 0)

    def test_analyser_sans_texte(self):
        reponse = self.client.post(self.url, {"texte_ia": "  ", "analyser": ""})
        self.assertContains(reponse, "abord")
        self.assertEqual(Transaction.objects.count(), 0)

    @mock.patch("atelier.views_finances.extraire_operation", side_effect=ErreurIA("Clé API Gemini manquante"))
    def test_erreur_ia_affichee_sans_planter(self, _extraire):
        reponse = self.client.post(self.url, {"texte_ia": "x", "analyser": ""})
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Clé API Gemini manquante")

    def test_enregistrer_fonctionne_toujours(self):
        reponse = self.client.post(self.url, {
            "date": "05/10/2026", "type": "DEPENSE", "categorie": "TISSU",
            "designation": "Soie", "montant": "120.00", "enregistrer": ""})
        self.assertRedirects(reponse, reverse("finances"))
        self.assertEqual(Transaction.objects.get().date, datetime.date(2026, 10, 5))

    @mock.patch("atelier.views_finances.extraire_operation")
    def test_endpoint_json_renvoie_une_date_iso(self, extraire):
        extraire.return_value = {"date": datetime.date(2026, 10, 5), "montant": 10.0}
        reponse = self.client.post(reverse("analyser_texte_ia"), json.dumps({"phrase": "x"}),
                                   content_type="application/json")
        self.assertEqual(reponse.json(), {"date": "2026-10-05", "montant": 10.0})

    @mock.patch("atelier.views_finances.extraire_operation", side_effect=ErreurIA("panne", status=502))
    def test_endpoint_json_propage_le_code_d_erreur(self, _extraire):
        reponse = self.client.post(reverse("analyser_texte_ia"), json.dumps({"phrase": "x"}),
                                   content_type="application/json")
        self.assertEqual(reponse.status_code, 502)


class MesuresIATests(ConnecteTestCase):
    url = property(lambda self: reverse("analyser_mesures_ia"))

    @mock.patch("atelier.views_atelier.extraire_mesures", return_value={"tour_taille": 68})
    def test_ok(self, _extraire):
        reponse = self.client.post(self.url, json.dumps({"texte": "taille 68"}), content_type="application/json")
        self.assertEqual(reponse.json(), {"tour_taille": 68})

    @mock.patch("atelier.views_atelier.extraire_mesures", side_effect=ErreurIA("Erreur de communication", status=502))
    def test_erreur_service(self, _extraire):
        reponse = self.client.post(self.url, json.dumps({"texte": "taille 68"}), content_type="application/json")
        self.assertEqual(reponse.status_code, 502)

    def test_validations(self):
        self.assertEqual(self.client.post(self.url, "pas du json", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(self.url, json.dumps({"texte": " "}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class ReinitialisationMotDePasseTests(TestCase):
    """Parcours complet : e-mail → code à 6 chiffres → nouveau mot de passe (views_auth)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = utilisateur_test("couturiere", "c@example.com", "AncienMdp123!")

    def test_parcours_complet(self):
        r = self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        self.assertRedirects(r, reverse("verifier_code_reset"))
        self.assertEqual(len(mail.outbox), 1)
        code = CodeReinitialisation.objects.get(user=self.user).code
        self.assertIn(code, mail.outbox[0].body)

        r = self.client.post(reverse("verifier_code_reset"), {"code": code})
        self.assertRedirects(r, reverse("nouveau_mot_de_passe"))

        r = self.client.post(reverse("nouveau_mot_de_passe"), {"password": "NouveauMdp456!", "password_confirm": "NouveauMdp456!"})
        self.assertRedirects(r, reverse("login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauMdp456!"))

    def test_email_inconnu_ne_revele_pas_que_le_compte_n_existe_pas(self):
        """Même réponse qu'un compte existant (pas d'énumération), mais aucun e-mail n'est envoyé."""
        connu = self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"}, follow=True)
        inconnu = self.client_class().post(reverse("demander_code_reset"), {"email": "inconnu@example.com"}, follow=True)

        self.assertEqual(connu.redirect_chain, inconnu.redirect_chain)
        self.assertEqual(connu.redirect_chain[-1][0], reverse("verifier_code_reset"))
        self.assertEqual(len(mail.outbox), 1)  # seul le compte réel a reçu un code
        for reponse in (connu, inconnu):
            self.assertContains(reponse, "Si un compte correspond")
            self.assertNotContains(reponse, "Aucun compte")

    def test_email_insensible_a_la_casse(self):
        self.client.post(reverse("demander_code_reset"), {"email": "C@Example.COM"})
        self.assertEqual(len(mail.outbox), 1)

    def test_code_a_six_chiffres(self):
        for _ in range(50):
            code = CodeReinitialisation.generer_code()
            self.assertRegex(code, r"^[1-9]\d{5}$")

    def test_pas_de_nouvel_envoi_dans_la_minute(self):
        for _ in range(3):
            self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(CodeReinitialisation.objects.filter(user=self.user).count(), 1)

    def test_un_echec_d_envoi_ne_plante_pas_la_page(self):
        with mock.patch("atelier.views_auth.send_mail", side_effect=OSError("SMTP indisponible")):
            with self.assertLogs("atelier.views_auth", level="ERROR"):
                r = self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        self.assertRedirects(r, reverse("verifier_code_reset"))

    def test_mauvais_code(self):
        self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        r = self.client.post(reverse("verifier_code_reset"), {"code": "000000"})
        self.assertContains(r, "invalide")

    def test_le_code_est_detruit_apres_trop_d_essais(self):
        """Impossible de deviner un code à 6 chiffres par force brute pendant les 10 minutes."""
        self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        vrai_code = CodeReinitialisation.objects.get(user=self.user).code
        faux = "000000" if vrai_code != "000000" else "111111"

        for _ in range(5):
            self.client.post(reverse("verifier_code_reset"), {"code": faux})
        self.assertFalse(CodeReinitialisation.objects.filter(user=self.user).exists())

        # Même le bon code ne passe plus : il faut en redemander un.
        r = self.client.post(reverse("verifier_code_reset"), {"code": vrai_code})
        self.assertContains(r, "invalide")
        self.assertNotIn("code_verifie", self.client.session)

    def test_mot_de_passe_trop_faible_refuse(self):
        self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        code = CodeReinitialisation.objects.get(user=self.user).code
        self.client.post(reverse("verifier_code_reset"), {"code": code})
        r = self.client.post(reverse("nouveau_mot_de_passe"), {"password": "12345678", "password_confirm": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AncienMdp123!"))

    def test_etapes_protegees(self):
        for nom in ("verifier_code_reset", "nouveau_mot_de_passe"):
            self.assertRedirects(self.client.get(reverse(nom)), reverse("demander_code_reset"))

    def test_mots_de_passe_differents(self):
        self.client.post(reverse("demander_code_reset"), {"email": "c@example.com"})
        code = CodeReinitialisation.objects.get().code
        self.client.post(reverse("verifier_code_reset"), {"code": code})
        r = self.client.post(reverse("nouveau_mot_de_passe"), {"password": "a", "password_confirm": "b"})
        self.assertContains(r, "ne correspondent pas")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AncienMdp123!"))


class ProgressionSansRequetesTests(ConnecteTestCase):
    def creer_robes(self, n):
        cliente = Client.objects.create(atelier=atelier_test(), nom="Test", prenom="Cliente")
        for i in range(n):
            robe = Robe.objects.create(client=cliente, nom_modele=f"R{i}", prix_total=100,
                                       date_commencement=datetime.date.today(),
                                       date_livraison=datetime.date.today() + datetime.timedelta(days=i + 1))
            for j in range(3):
                Tache.objects.create(robe=robe, libelle=f"T{j}", est_faite=(j == 0))

    def test_valeurs(self):
        cliente = Client.objects.create(atelier=atelier_test(), nom="Test", prenom="Cliente")
        robe = Robe.objects.create(client=cliente, nom_modele="R", date_commencement=datetime.date.today(),
                                   date_livraison=datetime.date.today())
        self.assertEqual(robe.progression, 0)
        for i, faite in enumerate((True, False, False)):
            Tache.objects.create(robe=robe, libelle=str(i), est_faite=faite)
        self.assertEqual(robe.progression, 33)
        robe.taches.filter(est_faite=False).first().delete()
        self.assertEqual(Robe.objects.get(pk=robe.pk).progression, 50)
        robe.taches.update(est_faite=True)
        self.assertEqual(Robe.objects.get(pk=robe.pk).progression, 100)

    def test_aucune_requete_quand_les_taches_sont_prechargees(self):
        self.creer_robes(1)
        robe = Robe.objects.prefetch_related("taches").get()
        with self.assertNumQueries(0):
            for _ in range(5):
                self.assertEqual(robe.progression, 33)

    def test_le_tableau_de_bord_n_a_pas_de_n_plus_un(self):
        def requetes():
            from django.db import connection
            from django.test.utils import CaptureQueriesContext
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
            return len(ctx)

        self.creer_robes(2)
        deux = requetes()
        self.creer_robes(6)
        huit = requetes()
        self.assertEqual(deux, huit, "le nombre de requêtes ne doit pas croître avec le nombre de robes")
