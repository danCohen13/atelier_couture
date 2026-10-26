"""Finances avancées : paiements, cautions, récurrentes, rentabilité, comparaisons, exports, documents."""
import csv
import datetime
import io
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from atelier.models import (
    Client,
    DepenseRecurrente,
    Location,
    Paiement,
    ParametresFinance,
    Robe,
    RobeLocation,
    Transaction,
)
from atelier.services import comptabilite as compta
from atelier.tests.outils import atelier_test, utilisateur_test


def jour(offset=0):
    return datetime.date.today() + datetime.timedelta(days=offset)


class Base(TestCase):
    def setUp(self):
        utilisateur_test('atelier', password='motdepasse123')
        self.client.login(username='atelier', password='motdepasse123')
        self.cliente = Client.objects.create(atelier=atelier_test(), nom='Dupont', prenom='Claire')
        self.stock = RobeLocation.objects.create(atelier=atelier_test(), 
            reference_stock='LOC-001', nom_modele='Aurore', taille='38', couleur='Ivoire',
            prix_location_defaut=Decimal('300'), caution_defaut=Decimal('500'), cout_revient=Decimal('1000'))

    def robe(self, prix='1000', tissu='200', livraison=0, devise='ILS', **kw):
        return Robe.objects.create(
            client=self.cliente, nom_modele='Robe A', date_commencement=jour(-30),
            date_livraison=jour(livraison), prix_total=Decimal(prix), cout_tissu=Decimal(tissu),
            devise=devise, **kw)

    def location(self, prix='300', caution='500', debut=0, **kw):
        return Location.objects.create(
            client=self.cliente, robe_location=self.stock, date_debut=jour(debut),
            date_fin_prevue=jour(debut + 3), prix_convenu=Decimal(prix), caution_montant=Decimal(caution), **kw)

    def lignes(self, **params):
        ctx = self.client.get(reverse('finances'), params).context
        return ctx, [l for g in ctx['groupes'] for l in g['lignes']]


class PaiementsTests(Base):
    def test_reste_a_payer_robe(self):
        robe = self.robe(prix='1000')
        Paiement.objects.create(robe=robe, montant=Decimal('400'))
        robe = Robe.objects.get(pk=robe.pk)
        self.assertEqual(robe.total_paye, Decimal('400'))
        self.assertEqual(robe.reste_a_payer, Decimal('600'))

    def test_ajout_via_la_page(self):
        robe = self.robe()
        r = self.client.post(reverse('paiements_robe', args=[robe.pk]), {
            'montant': '250', 'date': jour().strftime('%d/%m/%Y'), 'mode': 'VIREMENT', 'note': 'Acompte'})
        self.assertRedirects(r, reverse('paiements_robe', args=[robe.pk]))
        self.assertEqual(Paiement.objects.get().robe, robe)

    def test_paiement_superieur_au_reste_refuse(self):
        robe = self.robe(prix='100')
        r = self.client.post(reverse('paiements_robe', args=[robe.pk]), {
            'montant': '150', 'date': jour().strftime('%d/%m/%Y'), 'mode': 'ESPECES', 'note': ''})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Paiement.objects.exists())

    def test_montant_negatif_refuse(self):
        robe = self.robe()
        self.client.post(reverse('paiements_robe', args=[robe.pk]), {
            'montant': '-5', 'date': jour().strftime('%d/%m/%Y'), 'mode': 'ESPECES', 'note': ''})
        self.assertFalse(Paiement.objects.exists())

    def test_paiement_location_et_suppression_post_only(self):
        loc = self.location()
        self.client.post(reverse('paiements_location', args=[loc.pk]), {
            'montant': '100', 'date': jour().strftime('%d/%m/%Y'), 'mode': 'ESPECES', 'note': ''})
        p = Paiement.objects.get()
        self.assertEqual(p.location, loc)
        url = reverse('supprimer_paiement', args=[p.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(Paiement.objects.exists())

    def test_un_paiement_a_une_seule_cible(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            Paiement(montant=Decimal('10')).full_clean()

    def test_pages_protegees(self):
        self.client.logout()
        for nom in ('impayes', 'rentabilite', 'depenses_recurrentes', 'parametres_finance', 'exporter_csv',
                    'exporter_pdf_recapitulatif'):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 302, nom)

    def test_base_encaissee_compte_les_paiements(self):
        robe = self.robe(prix='1000', tissu='0')
        Paiement.objects.create(robe=robe, montant=Decimal('300'))
        ctx, _ = self.lignes()
        self.assertEqual(ctx['total_recettes'], Decimal('1000'))
        ctx, _ = self.lignes(base='encaisse')
        self.assertEqual(ctx['total_recettes'], Decimal('300'))


class CautionTests(Base):
    def test_caution_non_retenue_jamais_comptee(self):
        self.location(caution_statut='RESTITUEE')
        ctx, _ = self.lignes()
        self.assertEqual(ctx['total_recettes'], Decimal('300'))

    def test_caution_totalement_encaissee_devient_un_revenu(self):
        self.location(caution_statut='ENCAISSEE_TOTAL')
        ctx, lignes = self.lignes()
        self.assertEqual(ctx['total_recettes'], Decimal('800'))
        self.assertIn('Caution retenue (auto)', [l.get_categorie_display() for l in lignes])

    def test_caution_partielle(self):
        self.location(caution_statut='ENCAISSEE_PARTIEL', caution_retenue=Decimal('120'))
        ctx, _ = self.lignes()
        self.assertEqual(ctx['total_recettes'], Decimal('420'))

    def test_retenue_plafonnee_a_la_caution(self):
        loc = self.location(caution_statut='ENCAISSEE_PARTIEL', caution_retenue=Decimal('9999'))
        self.assertEqual(loc.caution_gardee, Decimal('500'))

    def test_formulaire_retour_valide_la_retenue(self):
        loc = self.location(statut='EN_COURS')
        url = reverse('retour_location', args=[loc.pk])
        donnees = {'date_retour_effectif': jour().strftime('%d/%m/%Y'), 'caution_statut': 'ENCAISSEE_PARTIEL',
                   'caution_retenue': '0', 'etat_apres': '', 'notes': ''}
        self.client.post(url, donnees)
        loc.refresh_from_db()
        self.assertEqual(loc.caution_statut, 'NON_DEPOSEE')  # refusé : retenue obligatoire
        donnees['caution_retenue'] = '600'
        self.client.post(url, donnees)
        loc.refresh_from_db()
        self.assertEqual(loc.caution_statut, 'NON_DEPOSEE')  # refusé : supérieure à la caution
        donnees['caution_retenue'] = '150'
        self.client.post(url, donnees)
        loc.refresh_from_db()
        self.assertEqual((loc.caution_statut, loc.caution_retenue), ('ENCAISSEE_PARTIEL', Decimal('150')))

    def test_retour_sans_retenue_renseignee_reste_valide(self):
        loc = self.location(statut='EN_COURS')
        self.client.post(reverse('retour_location', args=[loc.pk]), {
            'date_retour_effectif': jour().strftime('%d/%m/%Y'), 'caution_statut': 'RESTITUEE',
            'etat_apres': '', 'notes': ''})
        loc.refresh_from_db()
        self.assertEqual(loc.caution_statut, 'RESTITUEE')

    def test_cautions_a_suivre_et_alerte(self):
        self.location(statut='TERMINEE', caution_statut='ENREGISTREE', date_retour_effectif=jour())
        ctx, _ = self.lignes()
        self.assertEqual(ctx['cautions_detenues'][0]['montant'], Decimal('500'))
        self.assertTrue(any('caution' in a for a in ctx['alertes']))


class CreancesEtPrevisionnelTests(Base):
    def test_impayes_et_retard(self):
        retard = self.robe(prix='1000', livraison=-5)
        Paiement.objects.create(robe=retard, montant=Decimal('400'))
        elements = compta.creances(atelier_test())
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]['reste'], Decimal('600'))
        self.assertTrue(elements[0]['en_retard'])

    def test_robe_soldee_exclue_et_location_annulee_exclue(self):
        robe = self.robe(prix='100')
        Paiement.objects.create(robe=robe, montant=Decimal('100'))
        self.location(statut='ANNULEE')
        self.assertEqual(compta.creances(atelier_test()), [])

    def test_previsionnel_par_tranche(self):
        self.robe(prix='100', livraison=-2)
        Robe.objects.create(client=self.cliente, nom_modele='B', date_commencement=jour(-5),
                            date_livraison=jour(3), prix_total=Decimal('200'))
        Robe.objects.create(client=self.cliente, nom_modele='C', date_commencement=jour(-5),
                            date_livraison=jour(20), prix_total=Decimal('300'))
        Robe.objects.create(client=self.cliente, nom_modele='D', date_commencement=jour(-5),
                            date_livraison=jour(90), prix_total=Decimal('400'))
        tranches = {t['label']: t['montants'] for t in compta.previsionnel(compta.creances(atelier_test()))}
        self.assertEqual(tranches['En retard'][0]['montant'], Decimal('100'))
        self.assertEqual(tranches['Cette semaine'][0]['montant'], Decimal('200'))
        self.assertEqual(tranches['Dans le mois'][0]['montant'], Decimal('300'))
        self.assertEqual(tranches['Plus tard'][0]['montant'], Decimal('400'))

    def test_pages_impayes_et_finances_affichent(self):
        self.robe(prix='1000', livraison=-5)
        page = self.client.get(reverse('impayes'))
        self.assertContains(page, 'En retard')
        self.assertContains(page, 'Robe A')
        ctx, _ = self.lignes()
        self.assertTrue(any('retard' in a for a in ctx['alertes']))


class RecurrentesTests(Base):
    def test_generation_mensuelle_idempotente(self):
        rec = DepenseRecurrente.objects.create(atelier=atelier_test(), 
            designation='Loyer', montant=Decimal('2000'), categorie='AUTRE', jour_du_mois=1,
            date_debut=datetime.date(2026, 1, 1))
        n = compta.generer_depenses_recurrentes(atelier_test(), datetime.date(2026, 3, 15))
        self.assertEqual(n, 3)
        self.assertEqual(compta.generer_depenses_recurrentes(atelier_test(), datetime.date(2026, 3, 15)), 0)
        self.assertEqual(rec.transactions.count(), 3)
        self.assertEqual(compta.generer_depenses_recurrentes(atelier_test(), datetime.date(2026, 4, 2)), 1)

    def test_pas_d_ecriture_future_ni_inactive(self):
        DepenseRecurrente.objects.create(atelier=atelier_test(), designation='Futur', montant=Decimal('10'), jour_du_mois=20,
                                         date_debut=datetime.date(2026, 3, 1))
        DepenseRecurrente.objects.create(atelier=atelier_test(), designation='Pause', montant=Decimal('10'), actif=False,
                                         date_debut=datetime.date(2026, 1, 1))
        self.assertEqual(compta.generer_depenses_recurrentes(atelier_test(), datetime.date(2026, 3, 10)), 0)

    def test_crud_et_visibilite_dans_les_finances(self):
        r = self.client.post(reverse('depenses_recurrentes'), {
            'designation': 'Abonnement', 'montant': '50', 'categorie': 'AUTRE', 'jour_du_mois': '1',
            'date_debut': jour(-40).strftime('%d/%m/%Y')})
        self.assertRedirects(r, reverse('depenses_recurrentes'))
        rec = DepenseRecurrente.objects.get()
        self.assertGreaterEqual(rec.transactions.count(), 1)
        ctx, _ = self.lignes()
        self.assertGreaterEqual(ctx['total_depenses'], Decimal('50'))
        self.client.post(reverse('basculer_depense_recurrente', args=[rec.pk]))
        rec.refresh_from_db()
        self.assertFalse(rec.actif)
        ecritures = Transaction.objects.count()
        self.client.post(reverse('supprimer_depense_recurrente', args=[rec.pk]))
        self.assertFalse(DepenseRecurrente.objects.exists())
        self.assertEqual(Transaction.objects.count(), ecritures)  # historique conservé

    def test_jour_hors_plage_refuse(self):
        self.client.post(reverse('depenses_recurrentes'), {
            'designation': 'X', 'montant': '5', 'categorie': 'AUTRE', 'jour_du_mois': '31',
            'date_debut': jour().strftime('%d/%m/%Y')})
        self.assertFalse(DepenseRecurrente.objects.exists())


class OperationsTests(Base):
    def operation(self, **kw):
        defaults = dict(type='DEPENSE', montant=Decimal('40'), categorie='FOURNITURES',
                        designation='Fils', date=jour())
        defaults.update(kw)
        return Transaction.objects.create(atelier=atelier_test(), **defaults)

    def test_modifier(self):
        t = self.operation()
        r = self.client.post(reverse('modifier_transaction', args=[t.pk]), {
            'type': 'DEPENSE', 'montant': '55', 'categorie': 'MATERIEL', 'designation': 'Machine',
            'date': jour().strftime('%d/%m/%Y'), 'justificatif': 'https://res.cloudinary.com/x/ticket.jpg'})
        self.assertRedirects(r, reverse('finances'))
        t.refresh_from_db()
        self.assertEqual((t.montant, t.categorie), (Decimal('55'), 'MATERIEL'))
        self.assertEqual(t.justificatif, 'https://res.cloudinary.com/x/ticket.jpg')

    def test_supprimer_est_post_only(self):
        t = self.operation()
        url = reverse('supprimer_transaction', args=[t.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Transaction.objects.exists())
        self.client.post(url)
        self.assertFalse(Transaction.objects.exists())

    def test_montant_nul_refuse(self):
        self.client.post(reverse('ajouter_transaction'), {
            'type': 'DEPENSE', 'montant': '0', 'categorie': 'AUTRE', 'designation': 'x',
            'date': jour().strftime('%d/%m/%Y')})
        self.assertFalse(Transaction.objects.exists())

    def test_justificatif_et_actions_dans_le_grand_livre(self):
        self.operation(justificatif='https://res.cloudinary.com/x/ticket.jpg')
        page = self.client.get(reverse('finances'))
        self.assertContains(page, 'https://res.cloudinary.com/x/ticket.jpg')
        self.assertContains(page, 'Modifier')

    def test_les_lignes_automatiques_n_ont_pas_d_actions(self):
        self.robe()
        _, lignes = self.lignes()
        self.assertTrue(all(l.transaction is None for l in lignes if l.auto))


class RentabiliteTests(Base):
    def test_robe_benefice_et_gain_horaire(self):
        robe = self.robe(prix='1000', tissu='200', heures_travail=Decimal('20'))
        Transaction.objects.create(atelier=atelier_test(), type='DEPENSE', montant=Decimal('50'), categorie='FOURNITURES',
                                   designation='Boutons', date=jour(), robe=robe)
        (r,) = compta.rentabilite_robes(atelier_test())
        self.assertEqual(r['benefice'], Decimal('750'))
        self.assertEqual(r['gain_horaire'], Decimal('37.50'))

    def test_pas_de_gain_horaire_sans_heures(self):
        self.robe()
        self.assertIsNone(compta.rentabilite_robes(atelier_test())[0]['gain_horaire'])

    def test_stock_amortissement(self):
        self.location(prix='300', caution_statut='ENCAISSEE_TOTAL')   # 300 + 500 conservée
        self.location(prix='400', debut=10)
        self.location(prix='999', debut=20, statut='ANNULEE')
        (r,) = compta.rentabilite_stock(atelier_test())
        self.assertEqual(r['nb_locations'], 2)
        self.assertEqual(r['revenus'], Decimal('1200'))
        self.assertEqual(r['amortissement'], Decimal('120.0'))
        self.assertTrue(r['amortie'])

    def test_stock_sans_cout_de_revient(self):
        self.stock.cout_revient = 0
        self.stock.save()
        self.assertIsNone(compta.rentabilite_stock(atelier_test())[0]['amortissement'])

    def test_page(self):
        self.robe()
        self.location()
        page = self.client.get(reverse('rentabilite'))
        self.assertContains(page, 'Robe A')
        self.assertContains(page, 'LOC-001')

    def test_formulaires_acceptent_les_nouveaux_champs_facultatifs(self):
        self.client.post(reverse('ajouter_robe_location'), {
            'reference_stock': 'LOC-9', 'nom_modele': 'Lune', 'taille': '38', 'couleur': 'Bleu',
            'devise': 'ILS', 'prix_location_defaut': '100', 'caution_defaut': '100',
            'statut_physique': 'DISPONIBLE'})
        self.assertEqual(RobeLocation.objects.get(reference_stock='LOC-9').cout_revient, 0)


class ComparaisonsEtGlobalTests(Base):
    def test_comparaison_mois_precedent_et_n_moins_1(self):
        params = ParametresFinance.charger(atelier_test())
        aujourdhui = datetime.date(2026, 5, 15)
        Transaction.objects.create(atelier=atelier_test(), type='RECETTE', montant=Decimal('1000'), categorie='AUTRE',
                                   designation='a', date=datetime.date(2026, 5, 2))
        Transaction.objects.create(atelier=atelier_test(), type='RECETTE', montant=Decimal('500'), categorie='AUTRE',
                                   designation='b', date=datetime.date(2026, 4, 20))
        Transaction.objects.create(atelier=atelier_test(), type='RECETTE', montant=Decimal('800'), categorie='AUTRE',
                                   designation='c', date=datetime.date(2025, 5, 20))
        comp = compta.comparaison_mensuelle(compta.construire_lignes(atelier_test()), params, aujourdhui)
        self.assertEqual([c['recettes'] for c in comp], [Decimal('1000'), Decimal('500'), Decimal('800')])
        self.assertEqual(comp[1]['evolution'], Decimal('100.0'))
        self.assertEqual(comp[2]['evolution'], Decimal('25.0'))

    def test_comparaison_janvier_regarde_decembre(self):
        Transaction.objects.create(atelier=atelier_test(), type='RECETTE', montant=Decimal('10'), categorie='AUTRE',
                                   designation='d', date=datetime.date(2025, 12, 31))
        comp = compta.comparaison_mensuelle(compta.construire_lignes(atelier_test()), ParametresFinance.charger(atelier_test()),
                                            datetime.date(2026, 1, 10))
        self.assertEqual(comp[1]['recettes'], Decimal('10'))

    def test_variation_sans_reference(self):
        self.assertIsNone(compta.variation(Decimal('5'), Decimal('0')))

    def test_repartition_depenses(self):
        for cat, m in (('FOURNITURES', '30'), ('FOURNITURES', '30'), ('MATERIEL', '40')):
            Transaction.objects.create(atelier=atelier_test(), type='DEPENSE', montant=Decimal(m), categorie=cat, designation='x', date=jour())
        rep = compta.repartition_depenses(compta.construire_lignes(atelier_test()), ParametresFinance.charger(atelier_test()))
        self.assertEqual(rep[0]['montant'], Decimal('60'))
        self.assertEqual(rep[0]['part'], Decimal('60.0'))

    def test_confection_vs_location(self):
        self.robe(prix='1000', tissu='200')
        self.location(prix='300')
        act = {a['label']: a for a in compta.repartition_activites(compta.construire_lignes(atelier_test()), ParametresFinance.charger(atelier_test()))}
        self.assertEqual(act['Confection sur mesure']['benefice'], Decimal('800'))
        self.assertEqual(act['Location']['recettes'], Decimal('300'))

    def test_total_global_avec_taux(self):
        self.location(prix='100', devise='EUR')
        self.location(prix='50', debut=10)
        params = ParametresFinance.charger(atelier_test())
        glob = compta.total_global(compta.construire_lignes(atelier_test()), params)
        self.assertEqual(glob['recettes'], Decimal('50'))
        self.assertEqual(glob['incomplet'], ['EUR'])
        params.taux_eur = Decimal('4')
        params.save()
        glob = compta.total_global(compta.construire_lignes(atelier_test()), params)
        self.assertEqual(glob['recettes'], Decimal('450.00'))
        self.assertEqual(glob['incomplet'], [])

    def test_page_affiche_le_total_global_quand_autre_devise(self):
        self.location(prix='100', devise='EUR')
        ctx, _ = self.lignes()
        self.assertIsNotNone(ctx['total_global'])
        self.assertEqual(ctx['total_recettes'], 0)  # jamais d'addition sans conversion

    def test_pas_de_total_global_en_shekels_seuls(self):
        self.location()
        self.assertIsNone(self.lignes()[0]['total_global'])


class ObjectifTests(Base):
    def test_sans_objectif(self):
        self.assertIsNone(self.lignes()[0]['objectif'])

    def test_progression(self):
        params = ParametresFinance.charger(atelier_test())
        params.objectif_mensuel = Decimal('1000')
        params.save()
        Transaction.objects.create(atelier=atelier_test(), type='RECETTE', montant=Decimal('250'), categorie='AUTRE',
                                   designation='x', date=jour())
        obj = self.lignes()[0]['objectif']
        self.assertEqual(obj['pct'], Decimal('25.0'))
        self.assertFalse(obj['atteint'])

    def test_barre_plafonnee_et_atteint(self):
        params = ParametresFinance.charger(atelier_test())
        params.objectif_mensuel = Decimal('100')
        params.save()
        Transaction.objects.create(atelier=atelier_test(), type='RECETTE', montant=Decimal('250'), categorie='AUTRE',
                                   designation='x', date=jour())
        obj = self.lignes()[0]['objectif']
        self.assertEqual(obj['pct_barre'], 100)
        self.assertTrue(obj['atteint'])

    def test_page_parametres(self):
        r = self.client.post(reverse('parametres_finance'), {
            'taux_eur': '4.05', 'taux_usd': '3.7', 'objectif_mensuel': '12000'})
        self.assertRedirects(r, reverse('parametres_finance'))
        p = ParametresFinance.charger(atelier_test())
        self.assertEqual((p.taux_eur, p.objectif_mensuel), (Decimal('4.05'), Decimal('12000')))
        self.assertEqual(ParametresFinance.objects.count(), 1)

    def test_taux_negatif_refuse(self):
        self.client.post(reverse('parametres_finance'), {'taux_eur': '-1'})
        self.assertIsNone(ParametresFinance.charger(atelier_test()).taux_eur)


class ExportsEtDocumentsTests(Base):
    def test_csv(self):
        self.robe(prix='1000', tissu='0')
        Transaction.objects.create(atelier=atelier_test(), type='DEPENSE', montant=Decimal('12.5'), categorie='AUTRE',
                                   designation='=HYPERLINK("http://x")', date=jour())
        r = self.client.get(reverse('exporter_csv'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        texte = r.content.decode('utf-8-sig')
        lignes = list(csv.reader(io.StringIO(texte), delimiter=';'))
        self.assertEqual(lignes[0][0], 'Date')
        self.assertTrue(any(c.startswith("'=HYPERLINK") for l in lignes for c in l))   # pas de formule
        self.assertTrue(any('1000.00' in l for l in lignes))

    def test_csv_respecte_la_periode(self):
        Transaction.objects.create(atelier=atelier_test(), type='DEPENSE', montant=Decimal('9'), categorie='AUTRE',
                                   designation='vieux', date=jour(-800))
        self.assertEqual(len(list(csv.reader(io.StringIO(
            self.client.get(reverse('exporter_csv'), {'periode': 'mois'}).content.decode('utf-8-sig')),
            delimiter=';'))), 1)

    def test_pdf_recapitulatif(self):
        self.robe()
        r = self.client.get(reverse('exporter_pdf_recapitulatif'))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_devis_et_facture_robe(self):
        robe = self.robe()
        for genre in ('devis', 'facture'):
            r = self.client.get(reverse('document_pdf', args=['robe', robe.pk, genre]))
            self.assertEqual(r['Content-Type'], 'application/pdf', genre)
            self.assertTrue(r.content.startswith(b'%PDF'))

    def test_documents_location_et_recu(self):
        loc = self.location()
        p = Paiement.objects.create(location=loc, montant=Decimal('100'))
        for genre in ('devis', 'facture'):
            self.assertEqual(self.client.get(reverse('document_pdf', args=['location', loc.pk, genre]))['Content-Type'],
                             'application/pdf')
        self.assertEqual(self.client.get(reverse('recu_paiement', args=[p.pk]))['Content-Type'], 'application/pdf')

    def test_document_inconnu_404(self):
        robe = self.robe()
        self.assertEqual(self.client.get(f'/finances/document/robe/{robe.pk}/avoir.pdf').status_code, 404)
        self.assertEqual(self.client.get(f'/finances/document/autre/{robe.pk}/devis.pdf').status_code, 404)

    def test_contenu_du_document_avec_mention(self):
        from atelier.views_documents import MENTION_DOCUMENT
        robe = self.robe()
        page = self.client.get(reverse('paiements_robe', args=[robe.pk]))
        self.assertContains(page, 'Facture PDF')
        self.assertIn('facture fiscale', MENTION_DOCUMENT)
