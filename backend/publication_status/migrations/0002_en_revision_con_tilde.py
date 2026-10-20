# -*- coding: utf-8 -*-
"""Pone tilde al estado "En Revision" -> "En Revisión".

Solo dato: el campo ``name`` es un CharField con unique, no choices,
y todo el codigo cruza por slug o por id — el nombre es lo que se lee
en el admin.
"""
from django.db import migrations


def poner_tilde(apps, schema_editor):
    PublicationStatus = apps.get_model(
        'publication_status', 'PublicationStatus')
    if PublicationStatus.objects.filter(name='En Revisión').exists():
        return
    PublicationStatus.objects.filter(
        slug='en-revision', name='En Revision').update(name='En Revisión')


class Migration(migrations.Migration):

    dependencies = [
        ('publication_status', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(poner_tilde, migrations.RunPython.noop),
    ]
