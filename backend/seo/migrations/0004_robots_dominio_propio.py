"""El robots.txt sembrado por 0002 sigue apuntando al dominio viejo.

0002_siembra dejo el sitemap en ``buscandoando.onrender.com`` y esa
fila (pk=1) es la que el panel sirve HOY (manda sobre el fichero del
build). Con la llegada del dominio propio (buscandoando.app,
17/nov/2026), esta migracion sustituye el dominio en la fila SIN tocar
ninguna otra cosa: si el colaborador ya la edito a mano, su texto
sobrevive — solo se cambia el onrender.com de dentro.

Idempotente: si no hay fila o ya no trae el dominio viejo, no hace
nada. La vuelta atras hace el cambio inverso, simetrico.
"""
from django.db import migrations

VIEJO = 'buscandoando.onrender.com'
NUEVO = 'buscandoando.app'


def adelante(apps, schema_editor):
    SeoRobots = apps.get_model('seo', 'SeoRobots')
    fila = SeoRobots.objects.filter(pk=1).first()
    if fila and VIEJO in fila.contenido:
        fila.contenido = fila.contenido.replace(VIEJO, NUEVO)
        fila.save(update_fields=['contenido'])


def atras(apps, schema_editor):
    SeoRobots = apps.get_model('seo', 'SeoRobots')
    fila = SeoRobots.objects.filter(pk=1).first()
    if fila and NUEVO in fila.contenido:
        fila.contenido = fila.contenido.replace(NUEVO, VIEJO)
        fila.save(update_fields=['contenido'])


class Migration(migrations.Migration):

    dependencies = [
        ('seo', '0003_alter_seoruta_ruta'),
    ]

    operations = [
        migrations.RunPython(adelante, atras),
    ]
