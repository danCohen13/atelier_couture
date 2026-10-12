"""Export CSV des écritures."""


def _cellule_sure(valeur):
    """Neutralise l'injection de formules à l'ouverture dans Excel / Sheets."""
    texte = str(valeur)
    return "'" + texte if texte[:1] in ('=', '+', '-', '@', '\t', '\r') else texte


def lignes_csv(lignes):
    """En-tête + lignes triées (date décroissante) prêtes pour csv.writer."""
    sortie = [['Date', 'Type', 'Catégorie', 'Désignation', 'Robe', 'Montant', 'Devise', 'Origine']]
    for l in sorted(lignes, key=lambda x: x.date, reverse=True):
        sortie.append([
            l.date.strftime('%d/%m/%Y'), 'Recette' if l.type == 'RECETTE' else 'Dépense',
            _cellule_sure(l.categorie_label), _cellule_sure(l.designation),
            _cellule_sure(l.robe.nom_modele) if l.robe else '', f"{l.montant:.2f}", l.devise,
            'Automatique' if l.auto else 'Saisie manuelle',
        ])
    return sortie
