"""Borrar todos los negocios y datos relacionados."""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from businesses.models import Business
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from business_images.models import BusinessImage

total = Business.objects.count()
print(f"Negocios encontrados: {total}")

if total == 0:
    print("No hay nada que borrar.")
else:
    BusinessImage.objects.all().delete()
    print("  Imagenes borradas.")
    BusinessHours.objects.all().delete()
    print("  Horarios borrados.")
    BusinessContact.objects.all().delete()
    print("  Contactos borrados.")
    BusinessLocation.objects.all().delete()
    print("  Ubicaciones borradas.")
    Business.objects.all().delete()
    print(f"  {total} negocios borrados.")
    print("Base de datos limpia.")
