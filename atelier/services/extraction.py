"""
Extraction de données structurées à partir de texte libre (dictée vocale, notes).

Ici vivent les consignes (prompts) propres à l'atelier ; le transport est dans gemini.py.
"""
import datetime

from django.utils import timezone, translation

from ..models import Transaction
from .gemini import generer_json

CHAMPS_MESURES = ("tour_poitrine", "tour_taille", "tour_hanches", "hauteur_buste", "longueur_robe")

_CONSIGNE_MESURES = """
Tu es un assistant technique d'atelier de haute couture.
Analyse les notes ou la dictée vocale de l'utilisateur et extrait les mesures corporelles de la cliente.

Tu dois obligatoirement renvoyer UNIQUEMENT un objet JSON pur avec la structure suivante (si une mesure n'est pas mentionnée, mets null) :
{
    "tour_poitrine": un nombre entier ou décimal,
    "tour_taille": un nombre entier ou décimal,
    "tour_hanches": un nombre entier ou décimal,
    "hauteur_buste": un nombre entier ou décimal,
    "longueur_robe": un nombre entier ou décimal
}

Ne fournis aucune explication, aucune balise de code markdown. Renvoie juste le dictionnaire JSON.

La dictée peut être en HÉBREU ou en français (parfois les deux mélangés). Toutes les mesures sont en centimètres.
- Les nombres peuvent être écrits en chiffres ou en toutes lettres : « תשעים ושתיים » = 92, « שבעים וחצי » = 70.5,
  « quatre-vingt-douze » = 92. Un séparateur décimal peut être « נקודה » ou « virgule ».
- Vocabulaire hébreu : היקף חזה / חזה = tour_poitrine ; היקף מותניים / מותן / מותניים = tour_taille ;
  היקף ירכיים / ירכיים / אגן = tour_hanches ; גובה חזה = hauteur_buste ; אורך שמלה / אורך = longueur_robe ;
  « ס״מ », « סנטימטר » ou « cm » désignent des centimètres.
- Ne devine jamais une mesure absente : mets null.
"""


def extraire_mesures(texte):
    """Renvoie un dict {champ: nombre | None}."""
    return generer_json(_CONSIGNE_MESURES, f"Texte à analyser : {texte}", timeout=20)


NOMS_LANGUES = {"he": "hébreu", "fr": "français"}

JOURS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _consigne_operation(aujourdhui, langue="fr"):
    # Libellés toujours en français dans la consigne : le modèle reçoit un vocabulaire stable.
    with translation.override("fr"):
        categories = ", ".join(f"{code} ({libelle})" for code, libelle in Transaction.CATEGORIE_CHOICES)
    jour = JOURS_FR[datetime.date.fromisoformat(aujourdhui).weekday()]
    langue_nom = NOMS_LANGUES.get(langue, "français")
    return f"""
Tu es un assistant comptable pour un atelier de haute couture.
Analyse la phrase de l'utilisateur et extrait les données sous la forme d'un objet JSON pur.
La date d'aujourd'hui est le {aujourdhui} ({jour}).

La phrase peut être en HÉBREU ou en français. Règles :
- « designation » : courte description, rédigée en {langue_nom} (la langue de l'interface), sans le montant.
- Dépense (DEPENSE) : « קניתי », « שילמתי », « הוצאה », « acheté », « payé ». Recette (RECETTE) : « קיבלתי »,
  « שילמה לי », « מקדמה », « הכנסה », « reçu », « encaissé ».
- Monnaie : « שקל », « שקלים », « ש״ח », « ₪ », « shekels » ; ne renvoie que le nombre.
- Les nombres peuvent être en toutes lettres (« ארבעים וחמישה » = 45, « cent vingt » = 120).
- Dates relatives : « אתמול » = hier, « שלשום » = avant-hier, « היום » = aujourd'hui, « מחר » = demain,
  « לפני שבוע » = il y a 7 jours, « ביום ראשון האחרון » = le dimanche passé. En Israël la semaine commence le dimanche.

Tu dois répondre UNIQUEMENT avec un objet JSON respectant exactement cette structure, sans texte autour ni balises markdown :
{{
    "date": "AAAA-MM-JJ (déduis la date par rapport à aujourd'hui ; si elle n'est pas précisée, utilise {aujourdhui})",
    "type": "RECETTE ou DEPENSE (en majuscules)",
    "categorie": "exactement un de ces codes : {categories}",
    "designation": "Description courte de l'opération (ex: Achat fil de soie)",
    "montant": 125.50
}}
Le montant est un nombre, sans symbole de devise.
"""


def extraire_operation(phrase, aujourdhui=None, langue="fr"):
    """
    Renvoie un dict prêt à servir de `initial` à TransactionForm :
    date (datetime.date), type, categorie (code valide), designation, montant.
    Les valeurs inexploitables sont simplement omises : l'utilisatrice complète le formulaire.
    """
    aujourdhui = aujourdhui or timezone.localdate()
    brut = generer_json(_consigne_operation(aujourdhui.isoformat(), langue), f"Phrase à analyser : {phrase}", timeout=10)
    if not isinstance(brut, dict):
        return {}

    initial = {}
    try:
        initial["date"] = datetime.date.fromisoformat(str(brut.get("date", ""))[:10])
    except ValueError:
        initial["date"] = aujourdhui

    type_op = str(brut.get("type", "")).upper()
    if type_op in dict(Transaction.TYPE_CHOICES):
        initial["type"] = type_op

    categorie = str(brut.get("categorie", "")).upper()
    initial["categorie"] = categorie if categorie in dict(Transaction.CATEGORIE_CHOICES) else "AUTRE"

    if brut.get("designation"):
        initial["designation"] = str(brut["designation"])[:255]
    try:
        initial["montant"] = abs(float(brut.get("montant")))
    except (TypeError, ValueError):
        pass
    return initial
