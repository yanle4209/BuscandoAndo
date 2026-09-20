"""
Migración de datos: copiar address -> street y city -> sector
"""
from django.db import migrations


def forward(apps, schema_editor):
    BusinessLocation = apps.get_model('business_locations', 'BusinessLocation')
    for loc in BusinessLocation.objects.all():
        # Copiar address a street si street está vacío
        if not loc.street and hasattr(loc, 'address'):
            loc.street = getattr(loc, 'address', '')
        # Copiar city a sector si sector está vacío
        if not loc.sector and hasattr(loc, 'city'):
            loc.sector = getattr(loc, 'city', '')
        # Copiar state a municipality si municipality está vacío
        if not loc.municipality and hasattr(loc, 'state'):
            loc.municipality = getattr(loc, 'state', '')
        loc.save()


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('business_locations', '0002_remove_businesslocation_address_and_more'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
