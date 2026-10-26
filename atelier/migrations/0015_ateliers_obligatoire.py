"""Le rattachement à un atelier devient obligatoire sur toutes les données."""
import django.db.models.deletion
from django.db import migrations, models

MODELES = ['client', 'robe', 'tache', 'robelocation', 'location', 'paiement', 'transaction',
           'depenserecurrente', 'incidentsecurite']


class Migration(migrations.Migration):

    dependencies = [
        ('atelier', '0014_ateliers_rattacher_donnees'),
    ]

    operations = [
        migrations.AlterField(
            model_name=nom,
            name='atelier',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='+', to='atelier.atelier'),
        )
        for nom in MODELES
    ] + [
        migrations.AlterField(
            model_name='parametresfinance',
            name='atelier',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT, related_name='parametres_finance',
                to='atelier.atelier'),
        ),
    ]
