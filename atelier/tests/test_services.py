import datetime
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings

from atelier.services import extraction
from atelier.services.gemini import ErreurIA, generer_json


def reponse_gemini(texte):
    """Fabrique une réponse HTTP factice au format de l'API Gemini."""
    r = mock.Mock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"candidates": [{"content": {"parts": [{"text": texte}]}}]}
    return r


@override_settings(GEMINI_API_KEY="cle-secrete", GEMINI_MODEL="modele-test")
class GeminiTests(SimpleTestCase):
    @mock.patch("atelier.services.gemini.requests.post")
    def test_cle_dans_l_en_tete_jamais_dans_l_url(self, post):
        post.return_value = reponse_gemini('{"a": 1}')
        self.assertEqual(generer_json("consigne", "texte"), {"a": 1})
        args, kwargs = post.call_args
        self.assertNotIn("cle-secrete", args[0])
        self.assertIn("modele-test", args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "cle-secrete")

    @mock.patch("atelier.services.gemini.requests.post")
    def test_retire_les_clotures_markdown(self, post):
        for brut in ('```json\n{"a": 1}\n```', '```\n{"a": 1}\n```', '  {"a": 1}  '):
            post.return_value = reponse_gemini(brut)
            self.assertEqual(generer_json("c", "t"), {"a": 1}, brut)

    @override_settings(GEMINI_API_KEY=None)
    def test_cle_manquante(self):
        with self.assertRaises(ErreurIA) as ctx:
            generer_json("c", "t")
        self.assertEqual(ctx.exception.status, 500)
        self.assertIn("GEMINI_API_KEY", ctx.exception.message)

    @mock.patch("atelier.services.gemini.requests.post", side_effect=requests.exceptions.ConnectTimeout("délai dépassé"))
    def test_erreur_reseau_donne_502(self, _post):
        with self.assertRaises(ErreurIA) as ctx:
            generer_json("c", "t")
        self.assertEqual(ctx.exception.status, 502)
        self.assertNotIn("cle-secrete", ctx.exception.message)

    @mock.patch("atelier.services.gemini.requests.post")
    def test_reponse_illisible_donne_500(self, post):
        post.return_value = reponse_gemini("ceci n'est pas du JSON")
        with self.assertRaises(ErreurIA) as ctx:
            generer_json("c", "t")
        self.assertEqual(ctx.exception.status, 500)

        post.return_value = mock.Mock(json=mock.Mock(return_value={"candidates": []}),
                                      raise_for_status=mock.Mock())
        with self.assertRaises(ErreurIA):
            generer_json("c", "t")


class ExtractionOperationTests(TestCase):
    AUJOURDHUI = datetime.date(2026, 10, 7)

    def extraire(self, brut):
        with mock.patch("atelier.services.extraction.generer_json", return_value=brut):
            return extraction.extraire_operation("peu importe", self.AUJOURDHUI)

    def test_reponse_complete(self):
        r = self.extraire({"date": "2026-10-05", "type": "depense", "categorie": "fournitures",
                           "designation": "Fil de soie", "montant": 45.5})
        self.assertEqual(r, {"date": datetime.date(2026, 10, 5), "type": "DEPENSE", "categorie": "FOURNITURES",
                             "designation": "Fil de soie", "montant": 45.5})

    def test_valeurs_invalides_sont_neutralisees(self):
        r = self.extraire({"date": "hier", "type": "???", "categorie": "Fournitures diverses", "montant": "beaucoup"})
        self.assertEqual(r["date"], self.AUJOURDHUI)       # date illisible → aujourd'hui
        self.assertNotIn("type", r)                         # laissé au choix de l'utilisatrice
        self.assertEqual(r["categorie"], "AUTRE")           # code inconnu → AUTRE
        self.assertNotIn("montant", r)

    def test_montant_negatif_devient_positif(self):
        self.assertEqual(self.extraire({"montant": -12}) ["montant"], 12.0)

    def test_reponse_non_dict(self):
        self.assertEqual(self.extraire(["pas", "un", "dict"]), {})

    def test_la_consigne_liste_les_vrais_codes_de_categorie(self):
        from atelier.models import Transaction
        consigne = extraction._consigne_operation("2026-10-07")
        for code, _ in Transaction.CATEGORIE_CHOICES:
            self.assertIn(code, consigne)
