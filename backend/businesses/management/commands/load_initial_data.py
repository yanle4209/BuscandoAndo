"""
Management command: python manage.py load_initial_data
Clears existing data and loads everything fresh from fixture.
All IDs are explicit to match the fixture exactly.
"""
import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection


class Command(BaseCommand):
    help = 'Clear and reload all initial data from fixture'

    def handle(self, *args, **options):
        self.stdout.write("=== Clearing existing data ===")
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            for table in [
                'business_images_businessimage',
                'business_hours_businesshours',
                'business_contacts_businesscontact',
                'business_locations_businesslocation',
                'businesses_business',
                'categories_category',
                'publication_status_publicationstatus',
                'operational_status_operationalstatus',
            ]:
                cursor.execute(f"DELETE FROM {table}")
                self.stdout.write(f"  Cleared {table}")
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        # Recreate publication statuses with explicit IDs
        self.stdout.write("\n=== Creating publication statuses ===")
        from publication_status.models import PublicationStatus
        statuses = [
            (1, 'en-revision', 'En Revision'),
            (2, 'publicado', 'Publicado'),
            (3, 'cancelado', 'Cancelado'),
        ]
        for sid, slug, name in statuses:
            PublicationStatus.objects.create(id=sid, slug=slug, name=name)
            self.stdout.write(f'  Created: {name} (id={sid})')

        # Recreate operational statuses with explicit IDs
        self.stdout.write("\n=== Creating operational statuses ===")
        from operational_status.models import OperationalStatus
        op_statuses = [
            (1, 'abierto', 'Abierto', '#22c55e'),
            (2, 'cerrado', 'Cerrado', '#ef4444'),
            (3, 'por-horario', 'Por Horario', '#f59e0b'),
            (4, 'cerrado-permanente', 'Cerrado Permanente', '#6b7280'),
        ]
        for sid, slug, name, color in op_statuses:
            OperationalStatus.objects.create(id=sid, slug=slug, name=name, color=color)
            self.stdout.write(f'  Created: {name} (id={sid})')

        # Recreate categories with explicit IDs matching the fixture
        self.stdout.write("\n=== Creating categories ===")
        from categories.models import Category
        categories_data = [
            (1, 'restaurantes', 'Restaurantes', 'utensils'),
            (2, 'salones-de-belleza', 'Salones de Belleza', 'scissors'),
            (3, 'talleres-mecanicos', 'Talleres Mecanicos', 'wrench'),
            (4, 'clinicas', 'Clinicas', 'stethoscope'),
            (5, 'tiendas', 'Tiendas', 'store'),
            (6, 'gimnasios', 'Gimnasios', 'dumbbell'),
            (7, 'escuelas', 'Escuelas', 'school'),
            (8, 'hoteles', 'Hoteles', 'hotel'),
            (9, 'servicios-profesionales', 'Servicios Profesionales', 'briefcase'),
            (10, 'tecnologia', 'Tecnologia', 'laptop'),
            (11, 'servicios', 'Servicios', 'tools'),
            (13, 'salud', 'Salud', 'heart-pulse'),
            (14, 'otros', 'Otros', 'ellipsis'),
            (15, 'deporte', 'Deporte', 'football'),
            (16, 'educacion', 'Educacion', 'graduation-cap'),
        ]
        for cat_id, slug, name, icon in categories_data:
            Category.objects.create(id=cat_id, slug=slug, name=name, icon=icon)
            self.stdout.write(f'  Created: {name} (id={cat_id})')

        # Reset all sequences to correct values
        self.stdout.write("\n=== Resetting sequences ===")
        with connection.cursor() as cursor:
            sequences = [
                ('publication_status_publicationstatus', 'id'),
                ('operational_status_operationalstatus', 'id'),
                ('categories_category', 'id'),
            ]
            for table, column in sequences:
                seq = f"{table}_{column}_seq"
                cursor.execute(f"SELECT setval('{seq}', (SELECT COALESCE(MAX({column}), 1) FROM {table}))")
                self.stdout.write(f"  Reset {seq}")

        # Load businesses from fixture
        self.stdout.write("\n=== Loading businesses from fixture ===")
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            'initial_data.json'
        )

        if os.path.exists(fixture_path):
            call_command('loaddata', fixture_path, verbosity=1)
            self.stdout.write(self.style.SUCCESS('Fixture loaded successfully!'))
        else:
            self.stdout.write(self.style.WARNING(f'Fixture not found at {fixture_path}'))

        from businesses.models import Business
        from business_images.models import BusinessImage
        from business_hours.models import BusinessHours
        from business_contacts.models import BusinessContact
        from business_locations.models import BusinessLocation

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Statuses: {PublicationStatus.objects.count()}, '
            f'Op Statuses: {OperationalStatus.objects.count()}, '
            f'Categories: {Category.objects.count()}, '
            f'Businesses: {Business.objects.count()}, '
            f'Locations: {BusinessLocation.objects.count()}, '
            f'Contacts: {BusinessContact.objects.count()}, '
            f'Hours: {BusinessHours.objects.count()}, '
            f'Images: {BusinessImage.objects.count()}'
        ))
