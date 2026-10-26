"""Isolation entre ateliers : un atelier ne voit, ne modifie et ne supprime JAMAIS les données d'un autre."""
import ast
import datetime
import inspect
import pathlib
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.test import TestCase
from django.urls import reverse

import atelier.forms as formulaires
from atelier import urls as urls_atelier
from atelier.forms import LocationForm, RobeForm, RobeLocationForm
from atelier.models import (
    Adhesion,
    Atelier,
    Client,
    DepenseRecurrente,
    Location,
    Paiement,
    ParametresFinance,
    Robe,
    RobeLocation,
    Tache,
    Transaction,
)
from atelier.services import comptabilite as compta


def jour(offset=0):
    return datetime.date.today() + datetime.timedelta(days=offset)


def creer_donnees(atelier, marque):
    """Un jeu complet de données pour un atelier ; `marque` rend chaque texte reconnaissable."""
    cliente = Client.objects.create(atelier=atelier, nom=f'Nom{marque}', prenom=f'Prenom{marque}')
    robe = Robe.objects.create(
        client=cliente, nom_modele=f'Robe{marque}', date_commencement=jour(-10), date_livraison=jour(5),
        prix_total=Decimal('900'), cout_tissu=Decimal('100'))
    tache = Tache.objects.create(robe=robe, libelle=f'Tache{marque}')
    stock = RobeLocation.objects.create(
        atelier=atelier, reference_stock=f'REF-{marque}', nom_modele=f'Stock{marque}', taille='38',
        couleur='Ivoire', prix_location_defaut=Decimal('300'), caution_defaut=Decimal('500'))
    location = Location.objects.create(
        client=cliente, robe_location=stock, date_debut=jour(2), date_fin_prevue=jour(4),
        prix_convenu=Decimal('300'), caution_montant=Decimal('500'))
    paiement = Paiement.objects.create(robe=robe, montant=Decimal('200'), note=f'Note{marque}')
    operation = Transaction.objects.create(
        atelier=atelier, type='DEPENSE', categorie='AUTRE', montant=Decimal('50'),
        designation=f'Operation{marque}', date=jour(-1))
    recurrente = DepenseRecurrente.objects.create(
        atelier=atelier, designation=f'Loyer{marque}', montant=Decimal('1000'), date_debut=jour(-40))
    return SimpleNamespace(atelier=atelier, marque=marque, cliente=cliente, robe=robe, tache=tache,
                           stock=stock, location=location, paiement=paiement, operation=operation,
                           recurrente=recurrente)


class IsolationBase(TestCase):
    def setUp(self):
        self.atelier_a = Atelier.objects.create(nom='Atelier A')
        self.atelier_b = Atelier.objects.create(nom='Atelier B')
        self.a = creer_donnees(self.atelier_a, 'AAA')
        self.b = creer_donnees(self.atelier_b, 'BBB')
        self.user_a = User.objects.create_user('utilisatrice_a', password='motdepasse123')
        self.user_b = User.objects.create_user('utilisatrice_b', password='motdepasse123')
        Adhesion.objects.create(user=self.user_a, atelier=self.atelier_a)
        Adhesion.objects.create(user=self.user_b, atelier=self.atelier_b)

    def connecter(self, nom):
        self.client.login(username=nom, password='motdepasse123')


class AccesTests(IsolationBase):
    def test_sans_atelier_acces_refuse(self):
        User.objects.create_user('orpheline', password='motdepasse123')
        self.connecter('orpheline')
        reponse = self.client.get(reverse('dashboard'))
        self.assertEqual(reponse.status_code, 403)
        self.assertContains(reponse, "aucun atelier", status_code=403)

    def test_atelier_suspendu_acces_refuse(self):
        Atelier.objects.filter(pk=self.atelier_a.pk).update(statut='SUSPENDU')
        self.connecter('utilisatrice_a')
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('finances')).status_code, 403)

    def test_utilisatrice_voit_son_atelier(self):
        self.connecter('utilisatrice_a')
        reponse = self.client.get(reverse('dashboard'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Atelier A')


class AdressesParNumeroTests(IsolationBase):
    """Toute adresse qui contient un numéro est introuvable pour l'autre atelier (lecture, modification, suppression)."""

    def cibles(self):
        a = self.a
        return {
            'fiche_cliente': {'client_id': a.cliente.id},
            'exporter_pdf_cliente': {'client_id': a.cliente.id},
            'modifier_client': {'client_id': a.cliente.id},
            'modifier_robe': {'robe_id': a.robe.id},
            'supprimer_robe': {'robe_id': a.robe.id},
            'ajouter_tache_rapide': {'robe_id': a.robe.id, 'type_tache': 'toile'},
            'ajouter_tache_personnalisee': {'robe_id': a.robe.id},
            'toggle_tache': {'tache_id': a.tache.id},
            'supprimer_tache': {'tache_id': a.tache.id},
            'modifier_transaction': {'pk': a.operation.id},
            'supprimer_transaction': {'pk': a.operation.id},
            'basculer_depense_recurrente': {'pk': a.recurrente.id},
            'supprimer_depense_recurrente': {'pk': a.recurrente.id},
            'paiements_robe': {'robe_id': a.robe.id},
            'paiements_location': {'location_id': a.location.id},
            'supprimer_paiement': {'paiement_id': a.paiement.id},
            'recu_paiement': {'paiement_id': a.paiement.id},
            'retour_location': {'pk': a.location.id},
            'information_remise': {'client_id': a.cliente.id},
            'supprimer_cliente': {'client_id': a.cliente.id},
        }

    def test_toutes_les_adresses_a_numero_sont_testees(self):
        """Une nouvelle adresse avec un numéro doit être ajoutée à `cibles` (et donc testée)."""
        avec_numero = {p.name for p in urls_atelier.urlpatterns if '<int:' in str(p.pattern)}
        couvertes = set(self.cibles()) | {'document_pdf'}
        self.assertEqual(avec_numero - couvertes, set(), "Adresse(s) avec numéro non couverte(s) par ces tests")

    def test_autre_atelier_ne_peut_rien_atteindre(self):
        self.connecter('utilisatrice_b')
        cibles = dict(self.cibles())
        for nom, kwargs in cibles.items():
            url = reverse(nom, kwargs=kwargs)
            lecture = self.client.get(url).status_code
            ecriture = self.client.post(url, {'libelle': 'x'}).status_code
            self.assertIn(lecture, (404, 405), f"GET {nom} → {lecture}")
            self.assertEqual(ecriture, 404, f"POST {nom} → {ecriture}")
        for type_, pk in (('robe', self.a.robe.id), ('location', self.a.location.id)):
            for genre in ('devis', 'facture'):
                url = reverse('document_pdf', kwargs={'type_': type_, 'pk': pk, 'genre': genre})
                self.assertEqual(self.client.get(url).status_code, 404, f"document {type_} {genre}")

    def test_rien_n_a_ete_modifie_ni_supprime(self):
        self.connecter('utilisatrice_b')
        for nom, kwargs in self.cibles().items():
            self.client.post(reverse(nom, kwargs=kwargs), {'libelle': 'x'})
        self.assertTrue(Client.objects.filter(pk=self.a.cliente.pk, anonymisee_le__isnull=True).exists())
        self.assertTrue(Robe.objects.filter(pk=self.a.robe.pk).exists())
        self.assertEqual(Tache.objects.get(pk=self.a.tache.pk).est_faite, False)
        self.assertTrue(Tache.objects.filter(pk=self.a.tache.pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=self.a.operation.pk).exists())
        self.assertTrue(DepenseRecurrente.objects.get(pk=self.a.recurrente.pk).actif)
        self.assertTrue(Paiement.objects.filter(pk=self.a.paiement.pk).exists())
        self.assertEqual(Location.objects.get(pk=self.a.location.pk).statut, 'RESERVEE')
        self.assertIsNone(Client.objects.get(pk=self.a.cliente.pk).information_remise_le)

    def test_prefill_par_parametre_d_adresse(self):
        """`?client_id=` et `?robe_id=` ne permettent pas de lire un élément d'un autre atelier."""
        self.connecter('utilisatrice_b')
        self.assertEqual(self.client.get(reverse('ajouter_robe'), {'client_id': self.a.cliente.id}).status_code, 404)
        self.assertEqual(self.client.get(reverse('creer_location'), {'client_id': self.a.cliente.id}).status_code, 404)
        self.assertEqual(self.client.get(reverse('creer_location'), {'robe_id': self.a.stock.id}).status_code, 404)

    def test_controle_son_propre_atelier_fonctionne(self):
        """Contre-épreuve : les mêmes adresses répondent normalement à l'atelier propriétaire."""
        self.connecter('utilisatrice_a')
        self.assertEqual(self.client.get(reverse('fiche_cliente', args=[self.a.cliente.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('paiements_robe', args=[self.a.robe.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('modifier_transaction', args=[self.a.operation.id])).status_code, 200)


class ListesEtExportsTests(IsolationBase):
    """Les pages de liste, le planning, les exports et les calculs ne montrent que l'atelier courant."""

    def pages(self):
        return [
            reverse('dashboard'), reverse('liste_clientes'), reverse('finances'),
            reverse('impayes'), reverse('rentabilite'), reverse('depenses_recurrentes'),
            reverse('catalogue_location'), reverse('tableau_bord_locations'),
            reverse('confidentialite'), reverse('planning'),
            reverse('exporter_csv'),
        ]

    def test_aucune_fuite_dans_les_pages(self):
        self.connecter('utilisatrice_b')
        for url in self.pages():
            reponse = self.client.get(url, {'periode': 'tout'})
            self.assertEqual(reponse.status_code, 200, url)
            contenu = reponse.content.decode('utf-8')
            self.assertNotIn('AAA', contenu, f"fuite sur {url}")

    def test_les_pages_montrent_bien_leurs_propres_donnees(self):
        self.connecter('utilisatrice_b')
        self.assertContains(self.client.get(reverse('liste_clientes')), 'NOMBBB')
        self.assertContains(self.client.get(reverse('catalogue_location')), 'REF-BBB')
        self.assertContains(self.client.get(reverse('exporter_csv'), {'periode': 'tout'}), 'OperationBBB')

    def test_planning_api_isole(self):
        self.connecter('utilisatrice_b')
        debut, fin = jour(-1), jour(30)
        reponse = self.client.get(reverse('api_planning_evenements'), {'start': debut.isoformat(), 'end': fin.isoformat()})
        texte = reponse.content.decode('utf-8')
        self.assertIn('BBB', texte)
        self.assertNotIn('AAA', texte)

    def test_calendrier_des_reservations_isole(self):
        """Le calendrier du contrat n'expose que les périodes réservées de l'atelier courant."""
        self.connecter('utilisatrice_b')
        reponse = self.client.get(reverse('creer_location'))
        periodes = reponse.context['periodes_reservees']
        self.assertIn(self.b.stock.id, periodes)
        self.assertNotIn(self.a.stock.id, periodes)
        self.assertNotContains(reponse, 'NomAAA')

    def test_calculs_comptables_isoles(self):
        self.assertTrue(all('AAA' not in l.designation for l in compta.construire_lignes(self.atelier_b)))
        self.assertTrue(any('AAA' in l.designation for l in compta.construire_lignes(self.atelier_a)))
        self.assertEqual({e['client'] for e in compta.creances(self.atelier_b)}, {self.b.cliente})
        self.assertEqual([r['robe'] for r in compta.rentabilite_robes(self.atelier_b)], [self.b.robe])

    def test_depenses_recurrentes_generees_pour_le_bon_atelier(self):
        compta.generer_depenses_recurrentes(self.atelier_a)
        self.assertTrue(Transaction.objects.de(self.atelier_a).filter(recurrente=self.a.recurrente).exists())
        self.assertFalse(Transaction.objects.de(self.atelier_b).filter(recurrente=self.a.recurrente).exists())
        self.assertFalse(Transaction.objects.filter(recurrente=self.b.recurrente).exists())

    def test_reglages_financiers_separes(self):
        ParametresFinance.charger(self.atelier_a).__class__.objects.filter(atelier=self.atelier_a).update(taux_eur=Decimal('4'))
        self.assertEqual(ParametresFinance.charger(self.atelier_a).taux_eur, Decimal('4'))
        self.assertIsNone(ParametresFinance.charger(self.atelier_b).taux_eur)

    def test_reglages_atelier_ne_modifient_que_le_sien(self):
        self.connecter('utilisatrice_b')
        self.client.post(reverse('reglages_atelier'), {'nom': 'Atelier B renommé', 'contact_confidentialite': 'b@example.com'})
        self.atelier_a.refresh_from_db()
        self.atelier_b.refresh_from_db()
        self.assertEqual(self.atelier_b.nom, 'Atelier B renommé')
        self.assertEqual(self.atelier_a.nom, 'Atelier A')


class LiensEntreAteliersTests(IsolationBase):
    """On ne peut pas relier un élément à un élément d'un autre atelier (formulaire, API ou code)."""

    def test_modele_refuse_une_cliente_d_un_autre_atelier(self):
        with self.assertRaises(ValidationError):
            Robe.objects.create(
                atelier=self.atelier_b, client=self.a.cliente, nom_modele='Intrus',
                date_commencement=jour(0), date_livraison=jour(3))

    def test_atelier_repris_du_parent(self):
        robe = Robe.objects.create(client=self.a.cliente, nom_modele='Hérite', date_commencement=jour(0), date_livraison=jour(3))
        self.assertEqual(robe.atelier_id, self.atelier_a.id)

    def test_paiement_et_tache_refusent_un_parent_etranger(self):
        with self.assertRaises(ValidationError):
            Paiement.objects.create(atelier=self.atelier_b, robe=self.a.robe, montant=Decimal('10'))
        with self.assertRaises(ValidationError):
            Tache.objects.create(atelier=self.atelier_b, robe=self.a.robe, libelle='x')

    def test_formulaire_robe_ne_propose_que_les_clientes_de_l_atelier(self):
        form = RobeForm(atelier=self.atelier_b)
        self.assertEqual(list(form.fields['client'].queryset), [self.b.cliente])
        donnees = {'client': self.a.cliente.id, 'nom_modele': 'Intrus', 'date_commencement': jour(0).strftime('%d/%m/%Y'),
                   'date_livraison': jour(3).strftime('%d/%m/%Y'), 'devise': 'ILS', 'cout_tissu': '0', 'cout_main_doeuvre': '0',
                   'prix_total': '0'}
        self.assertFalse(RobeForm(atelier=self.atelier_b, data=donnees).is_valid())

    def test_formulaire_location_ne_propose_que_l_atelier(self):
        form = LocationForm(atelier=self.atelier_b)
        self.assertEqual(list(form.fields['client'].queryset), [self.b.cliente])
        self.assertEqual(list(form.fields['robe_location'].queryset), [self.b.stock])

    def test_creation_de_robe_via_la_vue_refuse_la_cliente_d_un_autre_atelier(self):
        self.connecter('utilisatrice_b')
        avant = Robe.objects.count()
        self.client.post(reverse('ajouter_robe'), {
            'client': self.a.cliente.id, 'nom_modele': 'Intrus',
            'date_commencement': jour(0).strftime('%d/%m/%Y'), 'date_livraison': jour(3).strftime('%d/%m/%Y'),
            'devise': 'ILS', 'cout_tissu': '0', 'cout_main_doeuvre': '0', 'prix_total': '0'})
        self.assertEqual(Robe.objects.count(), avant)

    def test_creation_de_client_est_rattachee_a_l_atelier_courant(self):
        self.connecter('utilisatrice_b')
        self.client.post(reverse('ajouter_client'), {'nom': 'Nouvelle', 'prenom': 'Cliente'})
        nouvelle = Client.objects.get(nom='Nouvelle')
        self.assertEqual(nouvelle.atelier_id, self.atelier_b.id)

    def test_la_cle_atelier_ne_peut_pas_etre_forcee_par_formulaire(self):
        self.connecter('utilisatrice_b')
        self.client.post(reverse('ajouter_client'), {'nom': 'Forcée', 'prenom': 'Cliente', 'atelier': self.atelier_a.id})
        self.assertEqual(Client.objects.get(nom='Forcée').atelier_id, self.atelier_b.id)

    def test_reference_de_stock_unique_par_atelier_seulement(self):
        # la même référence est permise dans deux ateliers différents…
        RobeLocation.objects.create(
            atelier=self.atelier_b, reference_stock='REF-AAA', nom_modele='Autre', taille='40', couleur='Noir',
            prix_location_defaut=Decimal('100'), caution_defaut=Decimal('100'))
        # …mais pas deux fois dans le même atelier (contrôle du formulaire).
        donnees = {'reference_stock': 'REF-BBB', 'nom_modele': 'Doublon', 'taille': '38', 'couleur': 'Rouge',
                   'prix_location_defaut': '100', 'caution_defaut': '100', 'statut_physique': 'DISPONIBLE', 'devise': 'ILS'}
        form = RobeLocationForm(atelier=self.atelier_b, data=donnees)
        self.assertFalse(form.is_valid())
        self.assertIn('reference_stock', form.errors)
        donnees['reference_stock'] = 'REF-NOUVELLE'
        self.assertTrue(RobeLocationForm(atelier=self.atelier_b, data=donnees).is_valid())


class FiletDeSecuriteTests(TestCase):
    """Garde-fous sur le code : ils échouent si quelqu'un oublie le filtre par atelier."""

    MODELES = {'Client', 'Robe', 'Tache', 'RobeLocation', 'Location', 'Paiement', 'Transaction',
               'DepenseRecurrente', 'IncidentSecurite', 'ParametresFinance'}
    METHODES_AUTORISEES = {'de', 'create', 'bulk_create', 'get_or_create', 'none'}

    def fichiers_du_code(self):
        racine = pathlib.Path(inspect.getfile(urls_atelier)).parent
        return [p for p in racine.rglob('*.py')
                if not {'tests', 'migrations', 'management'} & set(p.parts)]

    def test_aucune_lecture_sans_filtre_par_atelier(self):
        fautes = []
        for chemin in self.fichiers_du_code():
            for noeud in ast.walk(ast.parse(chemin.read_text(encoding='utf-8'))):
                # Modele.objects.<méthode>
                if (isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Attribute)
                        and noeud.value.attr == 'objects' and isinstance(noeud.value.value, ast.Name)
                        and noeud.value.value.id in self.MODELES
                        and noeud.attr not in self.METHODES_AUTORISEES):
                    fautes.append(f"{chemin.name}:{noeud.lineno} {noeud.value.value.id}.objects.{noeud.attr}")
                # get_object_or_404(Modele, …) sans passer par .objects.de(…)
                if (isinstance(noeud, ast.Call) and getattr(noeud.func, 'id', '') == 'get_object_or_404'
                        and noeud.args and isinstance(noeud.args[0], ast.Name)
                        and noeud.args[0].id in self.MODELES):
                    fautes.append(f"{chemin.name}:{noeud.lineno} get_object_or_404({noeud.args[0].id}, …)")
        self.assertEqual(fautes, [], "Requête sans filtre par atelier : utiliser Modele.objects.de(atelier)")

    def test_aucun_formulaire_n_expose_la_cle_atelier(self):
        for nom, classe in inspect.getmembers(formulaires, inspect.isclass):
            if issubclass(classe, ModelForm):
                self.assertNotIn('atelier', classe.base_fields, f"{nom} expose le champ « atelier »")
                # La cible de la relation est vérifiée ailleurs ; ici : pas de champ 'atelier' soumis par l'utilisatrice.

    def test_toutes_les_pages_refusent_un_compte_sans_atelier(self):
        """Une utilisatrice connectée sans atelier reçoit 403 partout, sauf sur les pages d'authentification."""
        User.objects.create_user('orpheline', password='motdepasse123')
        self.client.login(username='orpheline', password='motdepasse123')
        exemptes = {'login', 'logout', 'demander_code_reset', 'verifier_code_reset', 'nouveau_mot_de_passe'}
        for motif in urls_atelier.urlpatterns:
            if motif.name in exemptes or 'views_auth' in getattr(motif.callback, '__module__', ''):
                continue
            kwargs = {k: ('x' if 'str' in str(motif.pattern) and k in ('type_tache', 'type_', 'genre') else 1)
                      for k in motif.pattern.regex.groupindex}
            if 'type_' in kwargs:
                kwargs.update(type_='robe')
            if 'genre' in kwargs:
                kwargs.update(genre='devis')
            if 'type_tache' in kwargs:
                kwargs.update(type_tache='toile')
            reponse = self.client.get(reverse(motif.name, kwargs=kwargs))
            self.assertEqual(reponse.status_code, 403, f"{motif.name} → {reponse.status_code}")
