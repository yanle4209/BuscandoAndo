"""
Importar negocios desde un archivo JSON.
Uso: python import_businesses.py archivo.json
"""
import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from businesses.models import Business
from categories.models import Category
from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours


def import_from_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    pub_status = PublicationStatus.objects.get(slug='en-revision')
    created_count = 0
    skipped_count = 0

    for item in data:
        slug = item.get('slug', '')

        if Business.objects.filter(slug=slug).exists():
            print(f"  SKIP: {item.get('name', '?')} (ya existe)")
            skipped_count += 1
            continue

        # Get category
        category = None
        cat_slug = item.get('category')
        if cat_slug:
            category = Category.objects.filter(slug=cat_slug).first()

        # Get operational status
        op_status = None
        op_slug = item.get('operational_status')
        if op_slug:
            op_status = OperationalStatus.objects.filter(slug=op_slug).first()

        # Create business
        business = Business.objects.create(
            name=item.get('name', ''),
            slug=slug,
            description=item.get('description', ''),
            short_description=item.get('short_description', ''),
            category=category,
            publication_status=pub_status,
            operational_status=op_status,
            is_featured=item.get('is_featured', False),
        )

        # Create location
        loc_data = item.get('location', {})
        if loc_data:
            BusinessLocation.objects.create(
                business=business,
                street=loc_data.get('street', loc_data.get('address', '')),
                sector=loc_data.get('sector', ''),
                municipality=loc_data.get('municipality', loc_data.get('city', '')),
                district=loc_data.get('district', ''),
                province=loc_data.get('province', loc_data.get('state', '')),
                postal_code=loc_data.get('postal_code', ''),
                country=loc_data.get('country', 'República Dominicana'),
                latitude=loc_data.get('latitude'),
                longitude=loc_data.get('longitude'),
            )

        # Create contact
        contact_data = item.get('contact', {})
        if contact_data:
            BusinessContact.objects.create(
                business=business,
                phone=contact_data.get('phone', ''),
                whatsapp=contact_data.get('whatsapp', ''),
                email=contact_data.get('email', ''),
                website=contact_data.get('website', ''),
            )

        # Create hours
        hours_data = item.get('hours', [])
        for h in hours_data:
            open_time = h.get('open_time')
            close_time = h.get('close_time')
            BusinessHours.objects.create(
                business=business,
                day=h.get('day', ''),
                open_time=open_time if open_time else None,
                close_time=close_time if close_time else None,
                is_closed=h.get('is_closed', False),
            )

        print(f"  CREADO: {business.name} (En Revision)")
        created_count += 1

    print(f"\nImportacion completada!")
    print(f"  Creados: {created_count}")
    print(f"  Omitidos: {skipped_count}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python import_businesses.py archivo.json")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"Error: No se encontro el archivo {filepath}")
        sys.exit(1)

    import_from_json(filepath)
