"""Sauvegarde chiffrée de toute la base, hors de la base elle-même.

Principe : `dumpdata` (JSON, indépendant de la version de PostgreSQL) → gzip → chiffrement Fernet →
dépôt dans un stockage compatible S3 (Cloudflare R2, Backblaze B2, AWS…) ou dans un dossier local.
Le fichier contient des données personnelles : il n'est JAMAIS écrit sans chiffrement.

Variables d'environnement :
    BACKUP_ENCRYPTION_KEY   clé Fernet (python manage.py sauvegarde --generer-cle) – à garder aussi hors de Render
    BACKUP_S3_BUCKET, BACKUP_S3_ENDPOINT, BACKUP_S3_ACCESS_KEY, BACKUP_S3_SECRET_KEY, BACKUP_S3_REGION (facultatif)
    BACKUP_PREFIX           dossier dans le bucket (défaut : sauvegardes/)
Les photos ne sont pas dans la base : elles restent chez Cloudinary (seules leurs adresses sont sauvegardées).
"""
import datetime
import gzip
import io
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.management import call_command

# Tables sans valeur à restaurer : sessions, verrous de connexion, codes à usage unique, journal d'admin.
EXCLUS = ['sessions', 'axes', 'contenttypes', 'auth.permission', 'admin.logentry', 'atelier.codereinitialisation']

MODELE_NOM = re.compile(r'^atelier-(\d{8})-(\d{6})\.json\.gz\.enc$')
JOURS_QUOTIDIENNES = 14
MOIS_CONSERVES = 12


class ErreurSauvegarde(Exception):
    pass


def cle_chiffrement():
    cle = getattr(settings, 'BACKUP_ENCRYPTION_KEY', '')
    if not cle:
        raise ErreurSauvegarde("BACKUP_ENCRYPTION_KEY n'est pas définie : une sauvegarde ne doit jamais être écrite en clair. "
                               "Génère une clé avec : python manage.py sauvegarde --generer-cle")
    try:
        return Fernet(cle.encode())
    except (ValueError, TypeError) as exc:
        raise ErreurSauvegarde("BACKUP_ENCRYPTION_KEY n'est pas une clé Fernet valide.") from exc


def generer_cle():
    return Fernet.generate_key().decode()


def nom_fichier(maintenant=None):
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    return f"atelier-{maintenant:%Y%m%d-%H%M%S}.json.gz.enc"


def date_du_fichier(nom):
    trouve = MODELE_NOM.match(Path(nom).name)
    if not trouve:
        return None
    return datetime.datetime.strptime(trouve.group(1) + trouve.group(2), '%Y%m%d%H%M%S').replace(tzinfo=datetime.timezone.utc)


def exporter_chiffre():
    """Octets chiffrés de toute la base."""
    fernet = cle_chiffrement()
    tampon = io.StringIO()
    call_command('dumpdata', exclude=EXCLUS, indent=None, stdout=tampon, verbosity=0)
    return fernet.encrypt(gzip.compress(tampon.getvalue().encode('utf-8')))


def dechiffrer(contenu):
    """Texte JSON d'une sauvegarde ; lève ErreurSauvegarde si la clé ne correspond pas."""
    try:
        return gzip.decompress(cle_chiffrement().decrypt(contenu)).decode('utf-8')
    except InvalidToken as exc:
        raise ErreurSauvegarde("Déchiffrement impossible : mauvaise clé ou fichier abîmé.") from exc


def a_supprimer(noms, maintenant=None):
    """Politique de conservation : tout pendant 14 jours, puis la première sauvegarde de chacun des 12 derniers mois."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    datees = sorted((d, n) for n in noms if (d := date_du_fichier(n)))
    limite = maintenant - datetime.timedelta(days=JOURS_QUOTIDIENNES)
    premiere_du_mois = {}
    for d, n in datees:
        premiere_du_mois.setdefault((d.year, d.month), n)
    mois_gardes = set(sorted(premiere_du_mois)[-MOIS_CONSERVES:])
    garde = {n for (d, n) in datees if d >= limite}
    garde |= {n for cle, n in premiere_du_mois.items() if cle in mois_gardes}
    return [n for _, n in datees if n not in garde]


class StockageLocal:
    def __init__(self, dossier):
        self.dossier = Path(dossier)
        self.dossier.mkdir(parents=True, exist_ok=True)

    def deposer(self, nom, contenu):
        (self.dossier / nom).write_bytes(contenu)

    def lister(self):
        return sorted(p.name for p in self.dossier.iterdir() if MODELE_NOM.match(p.name))

    def lire(self, nom):
        return (self.dossier / nom).read_bytes()

    def supprimer(self, nom):
        (self.dossier / nom).unlink()


class StockageS3:
    def __init__(self):
        import boto3  # chargé seulement ici : inutile pour les sauvegardes locales
        conf = settings
        if not (conf.BACKUP_S3_BUCKET and conf.BACKUP_S3_ACCESS_KEY and conf.BACKUP_S3_SECRET_KEY):
            raise ErreurSauvegarde("Stockage S3 incomplet : BACKUP_S3_BUCKET, BACKUP_S3_ACCESS_KEY et BACKUP_S3_SECRET_KEY sont requis.")
        self.bucket = conf.BACKUP_S3_BUCKET
        self.prefixe = conf.BACKUP_PREFIX
        self.client = boto3.client(
            's3', endpoint_url=conf.BACKUP_S3_ENDPOINT or None, region_name=conf.BACKUP_S3_REGION or None,
            aws_access_key_id=conf.BACKUP_S3_ACCESS_KEY, aws_secret_access_key=conf.BACKUP_S3_SECRET_KEY)

    def deposer(self, nom, contenu):
        self.client.put_object(Bucket=self.bucket, Key=self.prefixe + nom, Body=contenu)

    def lister(self):
        noms, jeton = [], None
        while True:
            args = {'Bucket': self.bucket, 'Prefix': self.prefixe}
            if jeton:
                args['ContinuationToken'] = jeton
            reponse = self.client.list_objects_v2(**args)
            noms += [o['Key'][len(self.prefixe):] for o in reponse.get('Contents', [])]
            jeton = reponse.get('NextContinuationToken')
            if not jeton:
                return sorted(n for n in noms if MODELE_NOM.match(n))

    def lire(self, nom):
        return self.client.get_object(Bucket=self.bucket, Key=self.prefixe + nom)['Body'].read()

    def supprimer(self, nom):
        self.client.delete_object(Bucket=self.bucket, Key=self.prefixe + nom)


def stockage(dossier=None):
    """Dossier local si demandé, sinon le bucket S3 configuré."""
    if dossier:
        return StockageLocal(dossier)
    return StockageS3()


def sauvegarder(depot, maintenant=None):
    """Crée la sauvegarde, la dépose, applique la rotation. Renvoie (nom, octets, supprimés)."""
    nom = nom_fichier(maintenant)
    contenu = exporter_chiffre()
    depot.deposer(nom, contenu)
    supprimes = a_supprimer(depot.lister(), maintenant)
    for ancien in supprimes:
        depot.supprimer(ancien)
    return nom, len(contenu), supprimes


def compter(texte_json):
    """{'atelier.client': 12, …} pour contrôler le contenu d'une sauvegarde."""
    import json
    total = {}
    for objet in json.loads(texte_json):
        total[objet['model']] = total.get(objet['model'], 0) + 1
    return total
