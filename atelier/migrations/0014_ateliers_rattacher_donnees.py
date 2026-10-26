"""Rattache les données existantes (jusqu'ici d'un seul atelier) à un premier atelier."""
from django.conf import settings
from django.db import migrations

MODELES = ['Client', 'Robe', 'Tache', 'RobeLocation', 'Location', 'Paiement', 'Transaction',
           'DepenseRecurrente', 'IncidentSecurite', 'ParametresFinance']


def rattacher(apps, schema_editor):
    Atelier = apps.get_model('atelier', 'Atelier')
    Adhesion = apps.get_model('atelier', 'Adhesion')
    User = apps.get_model('auth', 'User')
    modeles = [apps.get_model('atelier', nom) for nom in MODELES]

    if not (User.objects.exists() or any(m.objects.exists() for m in modeles)):
        return  # installation neuve : les ateliers seront créés ensuite (invitations)

    atelier = Atelier.objects.create(
        nom=getattr(settings, 'ATELIER_NOM', '') or 'Mon atelier',
        contact_confidentialite=getattr(settings, 'CONTACT_CONFIDENTIALITE', '') or '',
    )
    for modele in modeles:
        modele.objects.filter(atelier__isnull=True).update(atelier=atelier)
    for user in User.objects.filter(adhesion__isnull=True):
        Adhesion.objects.create(user=user, atelier=atelier, role='PROPRIETAIRE')


class Migration(migrations.Migration):

    dependencies = [
        ('atelier', '0013_ateliers_ajout'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(rattacher, migrations.RunPython.noop),
    ]
