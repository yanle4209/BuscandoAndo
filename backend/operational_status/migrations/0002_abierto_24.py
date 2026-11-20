from django.db import migrations


def crear_abierto_24(apps, schema_editor):
    """«Abierto 24 horas»: estado que anula el requerimiento de horario.

    Idempotente a proposito: bases que ya lo tengan creado a mano (o
    un load_initial_data --force posterior) no duplican nada.
    """
    OperationalStatus = apps.get_model('operational_status', 'OperationalStatus')
    OperationalStatus.objects.get_or_create(
        slug='abierto-24',
        defaults={'name': 'Abierto 24 horas', 'color': '#16a34a'},
    )


def noop(apps, schema_editor):
    # Reversa inocua: un estado extra en el catalogo no estorba y asi
    # no se pierde si alguna ficha ya apunta a el.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('operational_status', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_abierto_24, noop),
    ]
