"""
Management command: python manage.py load_initial_data
Creates statuses, categories, and loads businesses from fixture.
Uses slug as lookup to avoid duplicate key errors from partial previous runs.
"""
import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus
from categories.models import Category


class Command(BaseCommand):
    help = 'Load initial data: statuses, categories, and businesses from fixture'

    def handle(self, *args, **options):
        # Publication statuses
        statuses = [
            ('en-revision', 'En Revision'),
            ('publicado', 'Publicado'),
            ('cancelado', 'Cancelado'),
        ]
        for slug, name in statuses:
            obj, created = PublicationStatus.objects.get_or_create(
                slug=slug, defaults={'name': name}
            )
            if created:
                self.stdout.write(f'  Created: {name}')

        # Operational statuses
        op_statuses = [
            ('abierto', 'Abierto', '#22c55e'),
            ('cerrado', 'Cerrado', '#ef4444'),
            ('por-horario', 'Por Horario', '#f59e0b'),
            ('cerrado-permanente', 'Cerrado Permanente', '#6b7280'),
        ]
        for slug, name, color in op_statuses:
            obj, created = OperationalStatus.objects.get_or_create(
                slug=slug, defaults={'name': name, 'color': color}
            )
            if created:
                self.stdout.write(f'  Created: {name}')

        # Categories - use slug as lookup to avoid duplicates from previous partial runs
        from django.utils.text import slugify
        categories_data = [
            ('restaurantes', 'Restaurantes', 'utensils'),
            ('salones-de-belleza', 'Salones de Belleza', 'scissors'),
            ('talleres-mecanicos', 'Talleres Mecanicos', 'wrench'),
            ('clinicas', 'Clinicas', 'stethoscope'),
            ('tiendas', 'Tiendas', 'store'),
            ('gimnasios', 'Gimnasios', 'dumbbell'),
            ('escuelas', 'Escuelas', 'school'),
            ('hoteles', 'Hoteles', 'hotel'),
            ('servicios-profesionales', 'Servicios Profesionales', 'briefcase'),
            ('tecnologia', 'Tecnologia', 'laptop'),
            ('servicios', 'Servicios', 'tools'),
            ('salud', 'Salud', 'heart-pulse'),
            ('otros', 'Otros', 'ellipsis'),
            ('deporte', 'Deporte', 'football'),
            ('educacion', 'Educacion', 'graduation-cap'),
        ]
        for slug, name, icon in categories_data:
            obj, created = Category.objects.get_or_create(
                slug=slug, defaults={'name': name, 'icon': icon}
            )
            if created:
                self.stdout.write(f'  Created: {name}')

        # Build a mapping of slug -> id for the fixture
        slug_to_id = {c.slug: c.id for c in Category.objects.all()}
        self.stdout.write(f'  Category mapping: {slug_to_id}')

        # Load businesses from fixture
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            'initial_data.json'
        )

        if os.path.exists(fixture_path):
            self.stdout.write(f'Loading fixture from {fixture_path}...')
            # Pre-process fixture to remap category IDs if needed
            import json
            with open(fixture_path, 'r', encoding='utf-8') as f:
                fixture_data = json.load(f)

            # Remap category_id in businesses to match production IDs
            local_slug_to_local_id = {}
            for item in fixture_data:
                if item['model'] == 'categories.category':
                    local_slug_to_local_id[item['fields']['slug']] = item['pk']

            # Build local_id -> production_id mapping
            id_remap = {}
            for slug, local_id in local_slug_to_local_id.items():
                if slug in slug_to_id:
                    id_remap[local_id] = slug_to_id[slug]

            if id_remap:
                remapped = 0
                for item in fixture_data:
                    if item['model'] == 'businesses.business':
                        old_id = item['fields'].get('category')
                        if old_id in id_remap:
                            item['fields']['category'] = id_remap[old_id]
                            remapped += 1
                self.stdout.write(f'  Remapped {remapped} business category IDs')

            # Write temporary fixed fixture
            tmp_fixture = fixture_path + '.tmp'
            with open(tmp_fixture, 'w', encoding='utf-8') as f:
                json.dump(fixture_data, f, ensure_ascii=False, indent=2)

            call_command('loaddata', tmp_fixture, verbosity=1)

            # Clean up temp file
            os.remove(tmp_fixture)

            self.stdout.write(self.style.SUCCESS('Fixture loaded successfully.'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Fixture not found at {fixture_path}. Only statuses/categories created.'
            ))

        from businesses.models import Business
        self.stdout.write(self.style.SUCCESS(
            f'Done! Statuses: {PublicationStatus.objects.count()}, '
            f'Op Statuses: {OperationalStatus.objects.count()}, '
            f'Categories: {Category.objects.count()}, '
            f'Businesses: {Business.objects.count()}'
        ))
