import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from atelier.forms import LocationForm, RetourLocationForm, RobeLocationForm
from atelier.models import Client, Location, RobeLocation


class LocationModelsTests(TestCase):
    """Vérification des règles métier sur les modèles RobeLocation et Location."""

    def setUp(self):
        self.cliente = Client.objects.create(nom="Lefebvre", prenom="Camille", telephone="+33611223344")
        self.robe_stock = RobeLocation.objects.create(
            reference_stock="LOC-001",
            nom_modele="Aurore",
            taille="38",
            couleur="Ivoire",
            prix_location_defaut=Decimal("150.00"),
            caution_defaut=Decimal("400.00"),
            statut_physique="DISPONIBLE",
        )

    def test_str_representations(self):
        self.assertIn("LOC-001", str(self.robe_stock))
        location = Location.objects.create(
            client=self.cliente,
            robe_location=self.robe_stock,
            date_debut=datetime.date.today(),
            date_fin_prevue=datetime.date.today() + datetime.timedelta(days=3),
            prix_convenu=Decimal("150.00"),
            caution_montant=Decimal("400.00"),
        )
        self.assertIn("Location #", str(location))
        self.assertIn("LOC-001", str(location))

    def test_disponibilite_statut_physique_bloquant(self):
        """Une robe en réparation ou hors-service n'est jamais disponible."""
        debut = datetime.date.today()
        fin = debut + datetime.timedelta(days=2)

        self.robe_stock.statut_physique = "REPARATION"
        self.robe_stock.save()
        self.assertFalse(self.robe_stock.est_disponible_sur_periode(debut, fin))

        self.robe_stock.statut_physique = "HORS_SERVICE"
        self.robe_stock.save()
        self.assertFalse(self.robe_stock.est_disponible_sur_periode(debut, fin))

    def test_anti_chevauchement_avec_tampon_pressing(self):
        """Vérifie le blocage des dates chevauchantes incluant les jours de battement pressing."""
        debut = datetime.date.today()
        fin = debut + datetime.timedelta(days=3)

        # Location active du J0 au J3 avec 2 jours de battement (bloquée jusqu'à J5)
        Location.objects.create(
            client=self.cliente,
            robe_location=self.robe_stock,
            date_debut=debut,
            date_fin_prevue=fin,
            delai_tampon_jours=2,
            prix_convenu=Decimal("150.00"),
            caution_montant=Decimal("400.00"),
            statut="RESERVEE",
        )

        # Chevauchement direct (J1 à J2) -> Refusé
        self.assertFalse(
            self.robe_stock.est_disponible_sur_periode(
                debut + datetime.timedelta(days=1), debut + datetime.timedelta(days=2)
            )
        )

        # Réservation sur le délai de tampon pressing (J4 à J5) -> Refusé
        self.assertFalse(
            self.robe_stock.est_disponible_sur_periode(
                debut + datetime.timedelta(days=4), debut + datetime.timedelta(days=5)
            )
        )

        # Réservation après le délai de tampon pressing (J6 à J8) -> Accepté
        self.assertTrue(
            self.robe_stock.est_disponible_sur_periode(
                debut + datetime.timedelta(days=6), debut + datetime.timedelta(days=8)
            )
        )

    def test_contrat_annule_ne_bloque_pas_le_calendrier(self):
        """Un contrat annulé libère immédiatement les dates de la pièce de stock."""
        debut = datetime.date.today()
        fin = debut + datetime.timedelta(days=3)

        Location.objects.create(
            client=self.cliente,
            robe_location=self.robe_stock,
            date_debut=debut,
            date_fin_prevue=fin,
            prix_convenu=Decimal("150.00"),
            caution_montant=Decimal("400.00"),
            statut="ANNULEE",
        )
        self.assertTrue(self.robe_stock.est_disponible_sur_periode(debut, fin))

    def test_validation_date_fin_anterieure_au_debut(self):
        """clean() doit lever une ValidationError si la date de fin précède le début."""
        loc = Location(
            client=self.cliente,
            robe_location=self.robe_stock,
            date_debut=datetime.date.today() + datetime.timedelta(days=5),
            date_fin_prevue=datetime.date.today(),
            prix_convenu=Decimal("150.00"),
            caution_montant=Decimal("400.00"),
        )
        with self.assertRaises(ValidationError):
            loc.clean()

    def test_propriete_est_en_retard(self):
        """Vérifie le déclenchement de l'alerte retard si la date de retour prévue est dépassée."""
        loc = Location.objects.create(
            client=self.cliente,
            robe_location=self.robe_stock,
            date_debut=datetime.date.today() - datetime.timedelta(days=5),
            date_fin_prevue=datetime.date.today() - datetime.timedelta(days=1),
            prix_convenu=Decimal("150.00"),
            caution_montant=Decimal("400.00"),
            statut="EN_COURS",
        )
        self.assertTrue(loc.est_en_retard)

        # Si la robe est restituée, elle n'est plus en retard
        loc.date_retour_effectif = datetime.date.today()
        loc.statut = "TERMINEE"
        loc.save()
        self.assertFalse(loc.est_en_retard)


class LocationFormsTests(TestCase):
    """Validation des formulaires d'inventaire et de contrats."""

    def setUp(self):
        self.cliente = Client.objects.create(nom="Bernard", prenom="Lucie")
        self.robe = RobeLocation.objects.create(
            reference_stock="LOC-002",
            nom_modele="Sirène",
            taille="36",
            couleur="Blanc",
            prix_location_defaut=Decimal("200.00"),
            caution_defaut=Decimal("500.00"),
        )

    def test_robe_location_form_valide(self):
        form = RobeLocationForm(data={
            'reference_stock': 'LOC-003',
            'nom_modele': 'Bohème Dentelle',
            'taille': '40',
            'couleur': 'Champagne',
            'prix_location_defaut': '180.00',
            'caution_defaut': '450.00',
            'statut_physique': 'DISPONIBLE',
            'description': 'Tulle soyeux',
            'etat_general': 'Parfait état',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_location_form_valide(self):
        form = LocationForm(data={
            'client': self.cliente.id,
            'robe_location': self.robe.id,
            'date_debut': datetime.date.today().strftime('%d/%m/%Y'),
            'date_fin_prevue': (datetime.date.today() + datetime.timedelta(days=4)).strftime('%d/%m/%Y'),
            'prix_convenu': '200.00',
            'caution_montant': '500.00',
            'caution_statut': 'ENREGISTREE',
            'delai_tampon_jours': 2,
            'statut': 'RESERVEE',
            'etat_avant': 'Impeccable au départ',
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_retour_location_form_valide(self):
        form = RetourLocationForm(data={
            'date_retour_effectif': datetime.date.today().strftime('%d/%m/%Y'),
            'caution_statut': 'RESTITUEE',
            'etat_apres': 'Robe rendue propre, aucun accroc.',
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors)


class LocationViewsTests(TestCase):
    """Tests fonctionnels des vues et du contrôle d'accès."""

    def setUp(self):
        self.user = User.objects.create_user(username="couturiere", password="Password123!")
        self.cliente = Client.objects.create(nom="Gautier", prenom="Chloé")
        self.robe = RobeLocation.objects.create(
            reference_stock="LOC-004",
            nom_modele="Princesse",
            taille="38",
            couleur="Poudre",
            prix_location_defaut=Decimal("220.00"),
            caution_defaut=Decimal("600.00"),
            statut_physique="DISPONIBLE",
        )
        self.location = Location.objects.create(
            client=self.cliente,
            robe_location=self.robe,
            date_debut=datetime.date.today(),
            date_fin_prevue=datetime.date.today() + datetime.timedelta(days=2),
            prix_convenu=Decimal("220.00"),
            caution_montant=Decimal("600.00"),
            statut="EN_COURS",
        )

    def test_toutes_les_vues_exigent_authentification(self):
        """Un utilisateur anonyme doit être redirigé vers la page de login."""
        urls = [
            reverse('catalogue_location'),
            reverse('ajouter_robe_location'),
            reverse('tableau_bord_locations'),
            reverse('creer_location'),
            reverse('retour_location', args=[self.location.id]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"La vue {url} n'est pas protégée !")
            self.assertIn(reverse('login'), response.url)

    def test_catalogue_avec_recherche_et_filtre(self):
        self.client.login(username="couturiere", password="Password123!")
        
        # Accès simple
        response = self.client.get(reverse('catalogue_location'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LOC-004")

        # Recherche par modèle
        response = self.client.get(reverse('catalogue_location') + "?q=Princesse")
        self.assertContains(response, "Princesse")

        # Recherche sans résultat
        response = self.client.get(reverse('catalogue_location') + "?q=Inexistant")
        self.assertNotContains(response, "LOC-004")

    def test_ajouter_robe_stock_post(self):
        self.client.login(username="couturiere", password="Password123!")
        data = {
            'reference_stock': 'LOC-010',
            'nom_modele': 'Empire Soie',
            'taille': '38',
            'couleur': 'Perle',
            'prix_location_defaut': '190.00',
            'caution_defaut': '400.00',
            'statut_physique': 'DISPONIBLE',
            'description': '',
            'etat_general': '',
        }
        response = self.client.post(reverse('ajouter_robe_location'), data=data)
        self.assertRedirects(response, reverse('catalogue_location'))
        self.assertTrue(RobeLocation.objects.filter(reference_stock='LOC-010').exists())

    def test_creer_location_avec_preremplissage_get(self):
        self.client.login(username="couturiere", password="Password123!")
        url = reverse('creer_location') + f"?client_id={self.cliente.id}&robe_id={self.robe.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Vérifie que les valeurs par défaut de la robe sont préremplies dans le contexte
        form = response.context['form']
        self.assertEqual(form.initial.get('prix_convenu'), self.robe.prix_location_defaut)
        self.assertEqual(form.initial.get('caution_montant'), self.robe.caution_defaut)

    def test_enregistrer_retour_location_post(self):
        self.client.login(username="couturiere", password="Password123!")
        retour_url = reverse('retour_location', args=[self.location.id])
        data = {
            'date_retour_effectif': datetime.date.today().strftime('%d/%m/%Y'),
            'caution_statut': 'RESTITUEE',
            'etat_apres': 'Robe restituée en parfait état.',
            'notes': '',
        }
        response = self.client.post(retour_url, data=data)
        self.assertRedirects(response, reverse('tableau_bord_locations'))

        self.location.refresh_from_db()
        self.assertEqual(self.location.statut, 'TERMINEE')
        self.assertEqual(self.location.caution_statut, 'RESTITUEE')
        self.assertEqual(self.location.date_retour_effectif, datetime.date.today())