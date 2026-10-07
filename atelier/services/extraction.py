"""
Extraction de données structurées à partir de texte libre (dictée vocale, notes).

Ici vivent les consignes (prompts) propres à l'atelier ; le transport est dans gemini.py.
"""
import datetime

from .gemini import generer_json
from ..models import Transaction

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
"""


def extraire_mesures(texte):
    """Renvoie un dict {champ: nombre | None}."""
    return generer_json(_CONSIGNE_MESURES, f"Texte à analyser : {texte}", timeout=20)


def _consigne_operation(aujourdhui):
    categories = ", ".join(f"{code} ({libelle})" for code, libelle in Transaction.CATEGORIE_CHOICES)
    return f"""
Tu es un assistant comptable pour un atelier de haute couture.
Analyse la phrase de l'utilisateur et extrait les données sous la forme d'un objet JSON pur.
La date d'aujourd'hui est le {aujourdhui}.

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


def extraire_operation(phrase, aujourdhui=None):
    """
    Renvoie un dict prêt à servir de `initial` à TransactionForm :
    date (datetime.date), type, categorie (code valide), designation, montant.
    Les valeurs inexploitables sont simplement omises : l'utilisatrice complète le formulaire.
    """
    aujourdhui = aujourdhui or datetime.date.today()
    brut = generer_json(_consigne_operation(aujourdhui.isoformat()), f"Phrase à analyser : {phrase}", timeout=10)
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
