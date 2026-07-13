from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Stockage statique recommandé par WhiteNoise en production : chaque
    fichier est renommé avec un hash de son contenu (ex: style.a1b2c3.css).

    C'est ce hash qui force le navigateur à recharger le CSS dès qu'il
    change au lieu de servir une version en cache — c'est ce qui manquait
    avec le stockage "simple" utilisé jusqu'ici, et qui causait un CSS
    visuellement périmé après chaque mise à jour du design.

    manifest_strict = False évite de faire planter le build si jamais un
    fichier référencé (police, image) est introuvable au moment du
    collectstatic, ce qui avait motivé l'abandon du stockage hashé.
    """
    manifest_strict = False
