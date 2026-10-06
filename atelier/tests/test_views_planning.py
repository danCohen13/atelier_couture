import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from atelier.models import Client, Location, Robe, RobeLocation, Tache


def jour(offset):
    return datetime.date.today() + datetime.timedelta(days=offset)


class PlanningBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="couturiere", password="Password123!")
        cls.cliente = Client.objects.create(nom="Gautier", prenom="Chloé", telephone="+33611223344")
        cls.stock = RobeLocation.objects.create(
            reference_stock="LOC-001", nom_modele="Aurore", taille="38", couleur="Ivoire",
            prix_location_defaut=Decimal("150.00"), caution_defaut=Decimal("400.00"),
        )

    def setUp(self):
        self.client.login(username="couturiere", password="Password123!")
        self.url = reverse("api_planning_evenements")

    def evenements(self, debut, fin):
        reponse = self.client.get(self.url, {"start": debut.isoformat(), "end": fin.isoformat()})
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    def location(self, **kw):
        defaults = dict(
            client=self.cliente, robe_location=self.stock,
            date_debut=jour(2), date_fin_prevue=jour(5),
            prix_convenu=Decimal("150.00"), caution_montant=Decimal("400.00"),
        )
        defaults.update(kw)
        return Location.objects.create(**defaults)


class PlanningAccesTests(PlanningBase):
    def test_pages_protegees(self):
        self.client.logout()
        for nom in ("planning", "api_planning_evenements"):
            reponse = self.client.get(reverse(nom))
            self.assertEqual(reponse.status_code, 302, nom)
            self.assertIn("/login/", reponse["Location"])

    def test_page_planning(self):
        reponse = self.client.get(reverse("planning"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'id="calendar"')
        self.assertContains(reponse, reverse("api_planning_evenements"))
        self.assertContains(reponse, "fullcalendar@6.1.15")

    def test_lien_dans_la_barre_laterale(self):
        reponse = self.client.get(reverse("dashboard"))
        self.assertContains(reponse, reverse("planning"))

    def test_api_refuse_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_parametres_invalides(self):
        for params in ({}, {"start": "2026-10-01"}, {"start": "n'importe quoi", "end": "2026-10-31"},
                       {"start": "2026-10-31", "end": "2026-10-01"},
                       {"start": "2026-01-01", "end": "2027-12-31"}):
            reponse = self.client.get(self.url, params)
            self.assertEqual(reponse.status_code, 400, params)
            self.assertIn("error", reponse.json())

    def test_format_fullcalendar_avec_fuseau(self):
        """FullCalendar envoie des datetimes ISO avec fuseau : seule la date compte."""
        Robe.objects.create(client=self.cliente, nom_modele="Robe A",
                            date_commencement=jour(-5), date_livraison=jour(3))
        reponse = self.client.get(self.url, {
            "start": f"{jour(0)}T00:00:00+02:00", "end": f"{jour(10)}T00:00:00+02:00"})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.json()), 1)


class PlanningLivraisonsTests(PlanningBase):
    def test_livraison_dans_la_periode(self):
        robe = Robe.objects.create(client=self.cliente, nom_modele="Robe de bal", prix_total=Decimal("1800"),
                                   date_commencement=jour(-10), date_livraison=jour(4))
        data = self.evenements(jour(0), jour(10))
        self.assertEqual(len(data), 1)
        ev = data[0]
        self.assertEqual(ev["id"], f"livraison-{robe.pk}")
        self.assertEqual(ev["title"], "Robe de bal")
        self.assertEqual(ev["start"], jour(4).isoformat())
        self.assertTrue(ev["allDay"])
        self.assertEqual(ev["extendedProps"]["kind"], "livraison")
        self.assertIn("ev--livraison", ev["classNames"])
        urls = [a["url"] for a in ev["extendedProps"]["actions"]]
        self.assertIn(reverse("modifier_robe", args=[robe.pk]), urls)
        self.assertIn(reverse("fiche_cliente", args=[self.cliente.pk]), urls)

    def test_borne_de_fin_exclue_borne_de_debut_incluse(self):
        Robe.objects.create(client=self.cliente, nom_modele="Début", date_commencement=jour(-5), date_livraison=jour(0))
        Robe.objects.create(client=self.cliente, nom_modele="Fin", date_commencement=jour(-5), date_livraison=jour(10))
        titres = [e["title"] for e in self.evenements(jour(0), jour(10))]
        self.assertEqual(titres, ["Début"])

    def test_hors_periode_absent(self):
        Robe.objects.create(client=self.cliente, nom_modele="Loin", date_commencement=jour(-5), date_livraison=jour(60))
        self.assertEqual(self.evenements(jour(0), jour(30)), [])

    def test_avancement_et_statut_echu(self):
        robe = Robe.objects.create(client=self.cliente, nom_modele="Passée", date_commencement=jour(-20), date_livraison=jour(-2))
        Tache.objects.create(robe=robe, libelle="Coupe", est_faite=True)
        Tache.objects.create(robe=robe, libelle="Finitions", est_faite=False)
        ev = self.evenements(jour(-5), jour(5))[0]
        self.assertIn(["Avancement", "50 %"], ev["extendedProps"]["lignes"])
        self.assertIn("ev--retard", ev["classNames"])        # date dépassée, pas terminée

        robe.taches.update(est_faite=True)
        ev = self.evenements(jour(-5), jour(5))[0]
        self.assertIn("ev--fait", ev["classNames"])
        self.assertNotIn("ev--retard", ev["classNames"])

    def test_nombre_de_requetes_constant(self):
        for i in range(8):
            robe = Robe.objects.create(client=self.cliente, nom_modele=f"R{i}",
                                       date_commencement=jour(-5), date_livraison=jour(i + 1))
            Tache.objects.create(robe=robe, libelle="x")
        with self.assertNumQueries(1 + 1 + 2 + 1 + 1):
            # session + utilisateur, robes, taches (prefetch), 2 requêtes locations
            self.evenements(jour(0), jour(30))


class PlanningLocationsTests(PlanningBase):
    def test_retrait_et_retour_sont_deux_evenements(self):
        loc = self.location(date_debut=jour(2), date_fin_prevue=jour(5))
        data = {e["id"]: e for e in self.evenements(jour(0), jour(10))}
        self.assertEqual(set(data), {f"retrait-{loc.pk}", f"retour-{loc.pk}"})
        self.assertEqual(data[f"retrait-{loc.pk}"]["start"], jour(2).isoformat())
        self.assertEqual(data[f"retour-{loc.pk}"]["start"], jour(5).isoformat())
        self.assertEqual(data[f"retrait-{loc.pk}"]["title"], "Aurore")
        self.assertIn("ev--retrait", data[f"retrait-{loc.pk}"]["classNames"])
        self.assertIn("ev--retour", data[f"retour-{loc.pk}"]["classNames"])

    def test_seul_le_retour_dans_la_periode(self):
        loc = self.location(date_debut=jour(-3), date_fin_prevue=jour(2))
        ids = [e["id"] for e in self.evenements(jour(0), jour(10))]
        self.assertEqual(ids, [f"retour-{loc.pk}"])

    def test_location_annulee_exclue(self):
        self.location(statut="ANNULEE")
        self.assertEqual(self.evenements(jour(0), jour(10)), [])

    def test_retour_en_retard(self):
        loc = self.location(date_debut=jour(-10), date_fin_prevue=jour(-2), statut="EN_COURS")
        data = {e["id"]: e for e in self.evenements(jour(-12), jour(5))}
        retour = data[f"retour-{loc.pk}"]
        self.assertIn("ev--retard", retour["classNames"])
        self.assertEqual(retour["extendedProps"]["kind_label"], "Retour en retard")
        self.assertIn("ev--fait", data[f"retrait-{loc.pk}"]["classNames"])   # déjà sortie
        libelles = [a["label"] for a in retour["extendedProps"]["actions"]]
        self.assertIn("Enregistrer le retour", libelles)

    def test_location_terminee_est_estompee(self):
        loc = self.location(date_debut=jour(-10), date_fin_prevue=jour(-2), statut="TERMINEE",
                            date_retour_effectif=jour(-2))
        retour = {e["id"]: e for e in self.evenements(jour(-12), jour(5))}[f"retour-{loc.pk}"]
        self.assertIn("ev--fait", retour["classNames"])
        self.assertNotIn("ev--retard", retour["classNames"])
        libelles = [a["label"] for a in retour["extendedProps"]["actions"]]
        self.assertNotIn("Enregistrer le retour", libelles)

    def test_reservation_future_sans_bouton_de_retour(self):
        loc = self.location(statut="RESERVEE")
        retour = {e["id"]: e for e in self.evenements(jour(0), jour(10))}[f"retour-{loc.pk}"]
        libelles = [a["label"] for a in retour["extendedProps"]["actions"]]
        self.assertNotIn("Enregistrer le retour", libelles)

    def test_details_de_la_location(self):
        loc = self.location()
        ev = {e["id"]: e for e in self.evenements(jour(0), jour(10))}[f"retrait-{loc.pk}"]
        props = ev["extendedProps"]
        self.assertEqual(props["telephone"], "+33611223344")
        self.assertEqual(props["client"], "GAUTIER Chloé")
        lignes = dict(props["lignes"])
        self.assertIn("LOC-001", lignes["Robe"])
        self.assertEqual(lignes["Tarif convenu"], "150.00 €")
        self.assertIn("400.00 €", lignes["Caution"])
