"""Las metas y el robots.txt de siempre, ahora editables (DISENO 15).

Los valores sembrados son EXACTAMENTE los que ya mandaba el codigo:
despues de esta migracion el sitio se ve igual que antes, pero lo que
se cambie a mano desde el panel rige al momento y sin desplegar.

Idempotente: si ya hay fila, no toca nada. La vuelta atras borra lo
sembrado — el codigo de valores por defecto sigue donde siempre, asi
que nada se pierde.
"""
from django.db import migrations

ROBOTS = """# robots.txt de BuscandoAndo (auditoria C).
#
# Vite copia este fichero tal cual a dist/ y serve_react lo sirve ANTES
# del fallback de la SPA (es un fichero real, no una ruta de React).
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: https://buscandoando.onrender.com/sitemap.xml
"""

METAS = [
    {
        'ruta': '',
        'titulo': ('BuscandoAndo - Encuentra negocios en República '
                   'Dominicana'),
        'descripcion': ('Directorio de negocios de República '
                        'Dominicana: encuentra restaurantes, farmacias, '
                        'talleres y más negocios cerca de ti con fotos, '
                        'horarios, teléfono y ubicación.'),
        'imagen': '',
        'noindex': False,
    },
    {
        'ruta': 'levantamiento',
        'titulo': 'Levantamiento de fichas | BuscandoAndo',
        'descripcion': ('Herramienta de captura de fichas de '
                        'BuscandoAndo para colaboradores de campo.'),
        'imagen': '',
        'noindex': True,
    },
]


def siembrar(apps, schema_editor):
    SeoRuta = apps.get_model('seo', 'SeoRuta')
    SeoRobots = apps.get_model('seo', 'SeoRobots')
    for metas in METAS:
        SeoRuta.objects.get_or_create(ruta=metas['ruta'], defaults=metas)
    if not SeoRobots.objects.filter(pk=1).exists():
        SeoRobots.objects.create(pk=1, contenido=ROBOTS)


def retirar(apps, schema_editor):
    SeoRuta = apps.get_model('seo', 'SeoRuta')
    SeoRobots = apps.get_model('seo', 'SeoRobots')
    SeoRuta.objects.filter(ruta__in=[m['ruta'] for m in METAS]).delete()
    SeoRobots.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('seo', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(siembrar, retirar),
    ]
