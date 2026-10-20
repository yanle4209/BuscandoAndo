# -*- coding: utf-8 -*-
"""Higiene de datos: nombres con tilde y descripciones de las categorias.

La auditoria externa de pre-lanzamiento (20/oct/2026) encontro
categorias sin acento ("Clinicas", "Educacion") y con la descripcion
vacia. Renombrar NO rompe nada:

* la busqueda (``busqueda.filtrar_por_texto``) normaliza tildes en los
  DOS lados, asi que "clinicas" sigue encontrando "Clínicas";
* ``masivo.categoria_de`` hace ``get_or_create(name=...)``: los mapas
  de OSM ya apuntan a los nombres con tilde, y esta migracion pone la
  base al mismo nivel — los dos cambios van juntos para que la proxima
  importacion no cree "Clinicas" nueva al lado de "Clínicas".
"""
from django.db import migrations

RENOMBROS = [
    ('Talleres Mecanicos', 'Talleres Mecánicos'),
    ('Clinicas', 'Clínicas'),
    ('Tecnologia', 'Tecnología'),
    ('Educacion', 'Educación'),
]

# Mismos textos que carga load_initial_data en una base nueva. Solo se
# rellenan descripciones VACIAS: lo que se haya escrito a mano en el
# admin se respeta.
DESCRIPCIONES = {
    'restaurantes': 'Restaurantes, comedores y cafés.',
    'salones-de-belleza': 'Peluquerías, salones de belleza y estética.',
    'talleres-mecanicos': 'Talleres mecánicos y servicios para tu vehículo.',
    'clinicas': 'Clínicas, consultorios médicos y dentistas.',
    'tiendas': 'Tiendas y comercios de todo tipo.',
    'gimnasios': 'Gimnasios y centros de entrenamiento.',
    'escuelas': 'Escuelas y centros educativos.',
    'hoteles': 'Hoteles y otros alojamientos.',
    'servicios-profesionales':
        'Contadores, abogados y otros profesionales.',
    'tecnologia': 'Servicios y productos de tecnología.',
    'servicios': 'Bancos, lavanderías, giros y otros servicios.',
    'salud': 'Hospitales, farmacias y servicios de salud.',
    'otros': 'Negocios que no entran en las demás categorías.',
    'deporte': 'Deportes, recreación y actividades al aire libre.',
    'educacion': 'Universidades, academias y formación.',
}


def higiene(apps, schema_editor):
    Category = apps.get_model('categories', 'Category')
    for vieja, nueva in RENOMBROS:
        # Si la nueva ya existe (renombrada a mano, o un duplicado
        # historico), no se toca: update contra unique_together.
        if Category.objects.filter(name=nueva).exists():
            continue
        Category.objects.filter(name=vieja).update(name=nueva)
    for slug, texto in DESCRIPCIONES.items():
        Category.objects.filter(slug=slug, description='').update(
            description=texto)


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0002_category_parent_alter_category_name_and_more'),
    ]

    operations = [
        # Irreversible a proposito: marchar atras un renombrado dejaria
        # los datos a medias sin que nadie lo pidiera.
        migrations.RunPython(higiene, migrations.RunPython.noop),
    ]
