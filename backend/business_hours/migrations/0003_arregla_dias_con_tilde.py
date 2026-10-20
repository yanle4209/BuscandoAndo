# -*- coding: utf-8 -*-
"""Arregla los dias de la semana que se guardaron sin tilde.

El importador de OSM (``osm.parse_hours`` / ``import_osm.parse_hours``)
mapeaba ``We -> 'Miercoles'`` y ``Sa -> 'Sabado'``, pero el modelo
exige ``'Miércoles'``/``'Sábado'`` (``BusinessHours.DayOfWeek``): Django
no valida choices al guardar, asi que las filas entraban y luego no
casaban con nada — ni con el orden del serializer ni con la deteccion
de estado por horario. Los mapas ya van corregidos; esta migracion
arregla lo que ya este en la base.

Defensiva: si un negocio ya tiene la fila buena para ese dia (unicidad
business+day) la fila mala se deja estar antes que romper la unica.
"""
from django.db import migrations


def arreglar(apps, schema_editor):
    BusinessHours = apps.get_model('business_hours', 'BusinessHours')
    for viejo, nuevo in (('Miercoles', 'Miércoles'),
                         ('Sabado', 'Sábado')):
        for fila in BusinessHours.objects.filter(day=viejo):
            if BusinessHours.objects.filter(
                    business_id=fila.business_id, day=nuevo).exists():
                continue
            fila.day = nuevo
            fila.save(update_fields=['day'])


class Migration(migrations.Migration):

    dependencies = [
        ('business_hours', '0002_businesshours_is_holiday'),
    ]

    operations = [
        migrations.RunPython(arreglar, migrations.RunPython.noop),
    ]
