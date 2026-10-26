"""Accueil public, connexion et inscription sur invitation."""
import io
import re
from datetime import timedelta

from django.contrib.admin.sites import site as site_admin  # noqa: F401  (charge l'admin)
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from atelier.models import Adhesion, Atelier, DemandeInvitation, Invitation

User = get_user_model()
MDP = 'Tr0mbone-Violette-92'


def donnees(**plus):
    base = {'nom_atelier': 'Atelier Léa', 'identifiant': 'lea', 'mot_de_passe': MDP, 'confirmation': MDP}
    base.update(plus)
    return base


class AccueilTests(TestCase):
    def test_accueil_public_en_hebreu_par_defaut(self):
        reponse = self.client.get(reverse('accueil'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'dir="rtl"')
        self.assertContains(reponse, reverse('login'))
        self.assertContains(reponse, 'name="robots" content="index, follow"')

    def test_accueil_en_francais(self):
        self.client.post(reverse('changer_langue'), {'langue': 'fr'})
        reponse = self.client.get(reverse('accueil'))
        self.assertContains(reponse, 'lang="fr"')
        self.assertContains(reponse, 'Chaque robe, de la première mesure à la livraison.')

    def test_en_tete_du_visiteur_propose_la_connexion(self):
        reponse = self.client.get(reverse('accueil'))
        self.assertContains(reponse, 'header-link--cta')
        self.assertNotContains(reponse, 'sidebar')

    def test_utilisatrice_connectee_voit_un_lien_vers_son_atelier(self):
        atelier = Atelier.objects.create(nom='Mon atelier')
        user = User.objects.create_user('a', password=MDP)
        Adhesion.objects.create(user=user, atelier=atelier, langue='fr')
        self.client.login(username='a', password=MDP)
        self.assertContains(self.client.get(reverse('accueil')), reverse('dashboard'))

    def test_l_application_est_sous_app(self):
        self.assertEqual(reverse('dashboard'), '/app/')
        self.assertEqual(reverse('login'), '/connexion/')
        reponse = self.client.get(reverse('dashboard'))
        self.assertRedirects(reponse, '/connexion/?next=/app/', fetch_redirect_response=False)

    def test_deconnexion_ramene_a_l_accueil(self):
        atelier = Atelier.objects.create(nom='Mon atelier')
        user = User.objects.create_user('a', password=MDP)
        Adhesion.objects.create(user=user, atelier=atelier)
        self.client.login(username='a', password=MDP)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('accueil'), fetch_redirect_response=False)

    def test_connexion_redirige_vers_l_application(self):
        atelier = Atelier.objects.create(nom='Mon atelier')
        user = User.objects.create_user('a', password=MDP)
        Adhesion.objects.create(user=user, atelier=atelier)
        reponse = self.client.post(reverse('login'), {'username': 'a', 'password': MDP})
        self.assertRedirects(reponse, reverse('dashboard'), fetch_redirect_response=False)


class InvitationModeleTests(TestCase):
    def test_seule_l_empreinte_est_conservee(self):
        invitation, jeton = Invitation.creer('lea@example.com', 'Atelier Léa')
        self.assertNotEqual(invitation.jeton_hash, jeton)
        self.assertNotIn(jeton, invitation.jeton_hash)
        self.assertEqual(Invitation.trouver(jeton), invitation)
        self.assertIsNone(Invitation.trouver('autre'))
        self.assertIsNone(Invitation.trouver(''))

    def test_validite(self):
        invitation, _ = Invitation.creer('lea@example.com')
        self.assertTrue(invitation.est_utilisable)
        Invitation.objects.filter(pk=invitation.pk).update(expire_le=timezone.now() - timedelta(seconds=1))
        invitation.refresh_from_db()
        self.assertFalse(invitation.est_utilisable)

    def test_refuse_une_adresse_deja_inscrite(self):
        User.objects.create_user('x', email='Lea@Example.com', password=MDP)
        with self.assertRaises(ValidationError):
            Invitation.creer('lea@example.com')

    def test_jetons_distincts(self):
        _, a = Invitation.creer('a@example.com')
        _, b = Invitation.creer('b@example.com')
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 40)


class AccepterInvitationTests(TestCase):
    def setUp(self):
        self.invitation, self.jeton = Invitation.creer('lea@example.com', 'Atelier proposé')
        self.url = reverse('accepter_invitation', args=[self.jeton])

    def test_formulaire_prerempli(self):
        reponse = self.client.get(self.url)
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Atelier proposé')
        self.assertContains(reponse, 'lea@example.com')

    def test_inscription_cree_atelier_compte_et_connecte(self):
        reponse = self.client.post(self.url, donnees())
        self.assertRedirects(reponse, reverse('dashboard'), fetch_redirect_response=False)
        utilisateur = User.objects.get(username='lea')
        self.assertEqual(utilisateur.email, 'lea@example.com')
        adhesion = utilisateur.adhesion
        self.assertEqual(adhesion.atelier.nom, 'Atelier Léa')
        self.assertEqual(adhesion.role, 'PROPRIETAIRE')
        self.assertEqual(adhesion.langue, 'he')
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.utilisee_le)
        self.assertEqual(self.invitation.atelier, adhesion.atelier)
        # Connectée : l'application s'ouvre sur son atelier.
        self.assertContains(self.client.get(reverse('dashboard')), 'Atelier Léa')

    def test_la_langue_choisie_est_retenue_sur_le_compte(self):
        self.client.post(reverse('changer_langue'), {'langue': 'fr'})
        self.client.post(self.url, donnees())
        self.assertEqual(User.objects.get(username='lea').adhesion.langue, 'fr')

    def test_lien_a_usage_unique(self):
        self.client.post(self.url, donnees())
        autre = self.client_class()
        reponse = autre.post(self.url, donnees(identifiant='lea2', nom_atelier='Autre'))
        self.assertEqual(reponse.status_code, 410)
        self.assertEqual(Atelier.objects.count(), 1)
        self.assertFalse(User.objects.filter(username='lea2').exists())
        self.assertEqual(autre.get(self.url).status_code, 410)

    def test_lien_expire(self):
        Invitation.objects.update(expire_le=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(self.url).status_code, 410)
        self.assertEqual(self.client.post(self.url, donnees()).status_code, 410)
        self.assertFalse(User.objects.exists())

    def test_lien_inconnu(self):
        reponse = self.client.get(reverse('accepter_invitation', args=['nimporte-quoi']))
        self.assertEqual(reponse.status_code, 410)

    def test_les_trois_cas_ont_la_meme_reponse(self):
        """Inconnu, expiré et utilisé : indiscernables pour un tiers."""
        inconnu = self.client.get(reverse('accepter_invitation', args=['zzz'])).content
        Invitation.objects.update(utilisee_le=timezone.now())
        utilise = self.client.get(self.url).content
        def nettoyer(page):
            page = re.sub(rb'csrfmiddlewaretoken" value="[^"]+"', b'', page)
            return re.sub(rb'/invitation/[^/"]+/', b'/invitation/X/', page)  # l'adresse elle-même est renvoyée par le sélecteur de langue
        self.assertEqual(nettoyer(inconnu), nettoyer(utilise))

    def test_mots_de_passe_differents(self):
        reponse = self.client.post(self.url, donnees(confirmation='autre'))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assertTrue(Invitation.objects.get().est_utilisable)

    def test_mot_de_passe_trop_faible(self):
        for faible in ('12345678', 'password', 'court1'):
            reponse = self.client.post(self.url, donnees(mot_de_passe=faible, confirmation=faible))
            self.assertEqual(reponse.status_code, 200, faible)
        self.assertFalse(User.objects.exists())

    def test_mot_de_passe_trop_proche_de_l_identifiant(self):
        reponse = self.client.post(self.url, donnees(identifiant='leapetitelea', mot_de_passe='leapetitelea', confirmation='leapetitelea'))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_identifiant_deja_pris_insensible_a_la_casse(self):
        User.objects.create_user('LEA', password=MDP)
        reponse = self.client.post(self.url, donnees())
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(Invitation.objects.get().est_utilisable)

    def test_deux_ateliers_ne_partagent_rien(self):
        self.client.post(self.url, donnees())
        _, jeton2 = Invitation.creer('zoe@example.com')
        autre = self.client_class()
        autre.post(reverse('accepter_invitation', args=[jeton2]),
                   donnees(nom_atelier='Atelier Zoé', identifiant='zoe'))
        self.assertEqual(Atelier.objects.count(), 2)
        self.assertNotEqual(User.objects.get(username='lea').adhesion.atelier,
                            User.objects.get(username='zoe').adhesion.atelier)


class EnvoiEtAdministrationTests(TestCase):
    @override_settings(SITE_URL='https://exemple.test')
    def test_commande_inviter_affiche_le_lien_et_envoie_l_email(self):
        sortie = io.StringIO()
        call_command('inviter', 'lea@example.com', 'Atelier Léa', '--envoyer', '--langue', 'fr', stdout=sortie)
        lien = sortie.getvalue().splitlines()[0]
        self.assertTrue(lien.startswith('https://exemple.test/invitation/'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['lea@example.com'])
        self.assertIn(lien, mail.outbox[0].body)
        self.assertIn('invitée', mail.outbox[0].body)
        self.assertEqual(self.client.get(lien.replace('https://exemple.test', '')).status_code, 200)

    def test_email_en_hebreu(self):
        sortie = io.StringIO()
        call_command('inviter', 'lea@example.com', '--envoyer', stdout=sortie)
        self.assertNotIn('invitée', mail.outbox[0].body)

    def test_commande_refuse_une_adresse_deja_inscrite(self):
        User.objects.create_user('x', email='lea@example.com', password=MDP)
        with self.assertRaises(CommandError):
            call_command('inviter', 'lea@example.com')

    def test_admin_cree_une_invitation_et_affiche_le_lien_une_fois(self):
        User.objects.create_superuser('root', 'root@example.com', MDP)
        self.client.login(username='root', password=MDP)
        from django.conf import settings
        url = f'/{settings.ADMIN_URL}atelier/invitation/add/'
        reponse = self.client.post(url, {'email': 'lea@example.com', 'nom_atelier': 'Atelier Léa'}, follow=True)
        self.assertEqual(reponse.status_code, 200)
        invitation = Invitation.objects.get()
        self.assertContains(reponse, '/invitation/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(invitation.est_utilisable)

    def test_admin_refuse_une_adresse_deja_inscrite(self):
        User.objects.create_user('x', email='lea@example.com', password=MDP)
        User.objects.create_superuser('root', 'root@example.com', MDP)
        self.client.login(username='root', password=MDP)
        from django.conf import settings
        self.client.post(f'/{settings.ADMIN_URL}atelier/invitation/add/', {'email': 'lea@example.com'})
        self.assertFalse(Invitation.objects.exists())

    def test_un_atelier_ne_peut_pas_creer_d_invitation(self):
        atelier = Atelier.objects.create(nom='A')
        user = User.objects.create_user('a', password=MDP)
        Adhesion.objects.create(user=user, atelier=atelier)
        self.client.login(username='a', password=MDP)
        from django.conf import settings
        reponse = self.client.get(f'/{settings.ADMIN_URL}atelier/invitation/add/')
        self.assertEqual(reponse.status_code, 302)  # vers la connexion de l'administration


class DemandeInvitationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.url = reverse('demander_invitation')

    def test_la_page_contient_le_formulaire_et_les_sections(self):
        page = self.client.get(reverse('accueil'))
        self.assertContains(page, 'id="demande"')
        self.assertContains(page, self.url)
        self.assertContains(page, 'name="site_web"')

    def test_demande_enregistree(self):
        reponse = self.client.post(self.url, {'email': 'lea@example.com', 'nom_atelier': 'Atelier Léa'}, follow=True)
        demande = DemandeInvitation.objects.get()
        self.assertEqual((demande.email, demande.nom_atelier, demande.traitee), ('lea@example.com', 'Atelier Léa', False))
        self.assertContains(reponse, 'lp-form-demande__msg--success')

    def test_pas_de_doublon_et_meme_reponse(self):
        self.client.post(self.url, {'email': 'lea@example.com'})
        reponse = self.client.post(self.url, {'email': 'LEA@example.com'}, follow=True)
        self.assertEqual(DemandeInvitation.objects.count(), 1)
        self.assertContains(reponse, 'lp-form-demande__msg--success')

    def test_adresse_deja_inscrite_recoit_la_meme_reponse(self):
        """On ne révèle pas si une adresse a déjà un compte."""
        User.objects.create_user('x', email='lea@example.com', password=MDP)
        reponse = self.client.post(self.url, {'email': 'lea@example.com'}, follow=True)
        self.assertContains(reponse, 'lp-form-demande__msg--success')

    def test_adresse_invalide(self):
        reponse = self.client.post(self.url, {'email': 'pas-une-adresse'}, follow=True)
        self.assertFalse(DemandeInvitation.objects.exists())
        self.assertContains(reponse, 'lp-form-demande__msg--error')

    def test_piege_a_robots(self):
        reponse = self.client.post(self.url, {'email': 'bot@example.com', 'site_web': 'http://spam'}, follow=True)
        self.assertFalse(DemandeInvitation.objects.exists())
        self.assertContains(reponse, 'lp-form-demande__msg--success')  # le robot ne sait pas qu'il a été écarté

    def test_limite_par_connexion(self):
        for i in range(6):
            self.client.post(self.url, {'email': f'a{i}@example.com'})
        self.assertEqual(DemandeInvitation.objects.count(), 5)

    def test_get_refuse(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(NOTIFIER_DEMANDES_A='moi@example.com')
    def test_notification_a_l_exploitante(self):
        self.client.post(self.url, {'email': 'lea@example.com', 'nom_atelier': 'Atelier Léa'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['moi@example.com'])
        self.assertIn('lea@example.com', mail.outbox[0].body)

    def test_action_admin_invite_et_marque_traitee(self):
        from django.conf import settings
        demande = DemandeInvitation.objects.create(email='lea@example.com', nom_atelier='Atelier Léa')
        User.objects.create_superuser('root', 'root@example.com', MDP)
        self.client.login(username='root', password=MDP)
        self.client.post(f'/{settings.ADMIN_URL}atelier/demandeinvitation/', {
            'action': 'inviter', '_selected_action': [demande.pk]}, follow=True)
        demande.refresh_from_db()
        self.assertTrue(demande.traitee)
        self.assertEqual(Invitation.objects.filter(email='lea@example.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)
