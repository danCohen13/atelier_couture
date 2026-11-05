from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('atelier', '0019_depenses_recurrentes_sans_doublon')]

    operations = [
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                fields=('recurrente', 'date'), name='depense_recurrente_unique_par_date'),
        ),
    ]
