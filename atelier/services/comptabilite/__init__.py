"""Calculs comptables de l'atelier (fonctions sans vue, faciles à tester).

Principes
---------
* Base « facturé » (par défaut) : une robe est comptée à sa date de livraison, une location à sa
  date de retrait. Base « encaissé » : on compte les paiements réellement reçus, à leur date.
* La caution n'est jamais un revenu, sauf la part conservée (dégâts, perte) : elle devient un
  revenu à la date de retour.
* Les montants de plusieurs devises ne sont jamais additionnés tels quels : les totaux « globaux »
  passent par les taux renseignés dans les paramètres (une devise sans taux est signalée).

Organisation : base (constantes) · ecritures · conversion · analyses · creances · rentabilite · export · tableau.
"""
from .analyses import comparaison_mensuelle, objectif_mensuel, repartition_activites, repartition_depenses, variation
from .base import DEVISE_PRINCIPALE, MOIS_FR, ZERO, LigneCompte
from .conversion import convertir_lignes, en_shekels, somme_par_devise, total_global
from .creances import alertes, cautions_a_suivre, creances, previsionnel
from .ecritures import bilan, construire_lignes, filtrer_periode, generer_depenses_recurrentes
from .export import lignes_csv
from .rentabilite import rentabilite_robes, rentabilite_stock
from .tableau import grouper_par_mois, tableau_de_bord

__all__ = [
    'DEVISE_PRINCIPALE', 'MOIS_FR', 'ZERO', 'LigneCompte', 'alertes', 'bilan', 'cautions_a_suivre',
    'charger_dossiers',
    'comparaison_mensuelle', 'construire_lignes', 'convertir_lignes', 'creances', 'en_shekels',
    'filtrer_periode', 'generer_depenses_recurrentes', 'grouper_par_mois', 'lignes_csv',
    'objectif_mensuel', 'previsionnel', 'rentabilite_robes', 'rentabilite_stock', 'repartition_activites',
    'repartition_depenses', 'somme_par_devise', 'tableau_de_bord', 'total_global', 'variation',
]
