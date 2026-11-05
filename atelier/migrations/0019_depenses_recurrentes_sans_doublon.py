from django.db import migrations


def supprimer_doublons(apps, schema_editor):
    """Garde la plus ancienne écriture de chaque (dépense récurrente, date) avant d'ajouter la contrainte."""
    Transaction = apps.get_model('atelier', 'Transaction')
    vues = set()
    a_supprimer = []
    for pk, rec, jour in (Transaction.objects.filter(recurrente__isnull=False)
                          .order_by('id').values_list('pk', 'recurrente_id', 'date')):
        if (rec, jour) in vues:
            a_supprimer.append(pk)
        vues.add((rec, jour))
    Transaction.objects.filter(pk__in=a_supprimer).delete()


class Migration(migrations.Migration):

    dependencies = [('atelier', '0018_demande_invitation')]

    operations = [migrations.RunPython(supprimer_doublons, migrations.RunPython.noop)]
