"""
Management command: python manage.py load_initial_data
Creates statuses, categories, and loads businesses from fixture.
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

        # Categories - all 16 that exist in the local database
        from django.utils.text import slugify
        categories = [
            (1, 'Restaurantes', 'utensils'),
            (2, 'Salones de Belleza', 'scissors'),
            (3, 'Talleres Mecanicos', 'wrench'),
            (4, 'Clinicas', 'stethoscope'),
            (5, 'Tiendas', 'store'),
            (6, 'Gimnasios', 'dumbbell'),
            (7, 'Escuelas', 'school'),
            (8, 'Hoteles', 'hotel'),
            (9, 'Servicios Profesionales', 'briefcase'),
            (10, 'Tecnologia', 'laptop'),
            (11, 'Servicios', 'tools'),
            (13, 'Salud', 'heart-pulse'),
            (14, 'Otros', 'ellipsis'),
            (15, 'Deporte', 'football'),
            (16, 'Educacion', 'graduation-cap'),
        ]
        for cat_id, name, icon in categories:
            slug = slugify(name, allow_unicode=True)
            obj, created = Category.objects.get_or_create(
                id=cat_id, defaults={'name': name, 'slug': slug, 'icon': icon}
            )
            if created:
                self.stdout.write(f'  Created: {name}')

        # Load businesses from fixture
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            'initial_data.json'
        )

        if os.path.exists(fixture_path):
            self.stdout.write(f'Loading fixture from {fixture_path}...')
            call_command('loaddata', fixture_path, verbosity=1)
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
