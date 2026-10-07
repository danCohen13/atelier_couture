"""
Client minimal pour l'API Gemini (Google).

C'est le SEUL endroit qui connaît l'URL, la clé et le modèle. Pour changer de
modèle ou de fournisseur, on modifie ce fichier (et GEMINI_MODEL dans les réglages).
"""
import json
import re

import requests
from django.conf import settings

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"

_CLOTURE_MARKDOWN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class ErreurIA(Exception):
    """Erreur présentable à l'utilisateur ; `status` est le code HTTP à renvoyer."""

    def __init__(self, message, status=500):
        super().__init__(message)
        self.message = message
        self.status = status


def _nettoyer_json(texte):
    """Retire les clôtures ```json … ``` que le modèle ajoute parfois malgré la consigne."""
    texte = texte.strip()
    trouve = _CLOTURE_MARKDOWN.match(texte)
    return trouve.group(1) if trouve else texte


def generer_json(consigne, texte, *, timeout=15):
    """
    Envoie `consigne` (rôle + format attendu) et `texte` (saisie à analyser) à Gemini
    et renvoie la réponse décodée (dict). Lève ErreurIA en cas de problème.
    """
    cle = settings.GEMINI_API_KEY
    if not cle:
        raise ErreurIA("Clé API Gemini manquante (GEMINI_API_KEY non configurée)", status=500)

    charge = {"contents": [{"parts": [{"text": consigne}, {"text": texte}]}]}
    try:
        reponse = requests.post(
            API_URL.format(modele=settings.GEMINI_MODEL),
            # La clé voyage dans un en-tête : elle n'apparaît ni dans l'URL ni dans les journaux d'erreurs.
            headers={"Content-Type": "application/json", "x-goog-api-key": cle},
            json=charge,
            timeout=timeout,
        )
        reponse.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ErreurIA(f"Erreur de communication avec l'API : {exc}", status=502) from exc

    try:
        brut = reponse.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(_nettoyer_json(brut))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ErreurIA(f"Impossible de décoder la réponse de l'IA : {exc}", status=500) from exc
