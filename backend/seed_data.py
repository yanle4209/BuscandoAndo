"""
Seed script para poblar estados iniciales.
Run: python manage.py shell < seed_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus
from categories.models import Category

print("=== Poblando estados de publicacion ===")
pub_statuses = [
    {'name': 'En Revision', 'slug': 'en-revision', 'description': 'Pendiente de revision por administrador', 'order': 1},
    {'name': 'Publicado', 'slug': 'publicado', 'description': 'Visible publicamente en el sitio', 'order': 2},
    {'name': 'Cancelado', 'slug': 'cancelado', 'description': 'Rechazado, no visible publicamente', 'order': 3},
]
for data in pub_statuses:
    obj, created = PublicationStatus.objects.get_or_create(slug=data['slug'], defaults=data)
    status = 'CREADO' if created else 'YA EXISTIA'
    print(f"  {status}: {obj.name}")

print("\n=== Poblando estados operativos ===")
op_statuses = [
    {'name': 'Abierto', 'slug': 'abierto', 'description': 'El negocio esta atendiendo', 'color': '#22c55e', 'order': 1},
    {'name': 'Cerrado', 'slug': 'cerrado', 'description': 'Cerrado por ahora, vuelve despues', 'color': '#ef4444', 'order': 2},
    {'name': 'Por Cerrar', 'slug': 'por-cerrar', 'description': 'A punto de cerrar', 'color': '#f59e0b', 'order': 3},
    {'name': 'Cerrado Permanentemente', 'slug': 'cerrado-permanente', 'description': 'No vuelve a abrir', 'color': '#6b7280', 'order': 4},
]
for data in op_statuses:
    obj, created = OperationalStatus.objects.get_or_create(slug=data['slug'], defaults=data)
    status = 'CREADO' if created else 'YA EXISTIA'
    print(f"  {status}: {obj.name}")

print("\n=== Poblando categorias ===")
categories = [
    {'name': 'Restaurantes', 'slug': 'restaurantes', 'icon': 'utensils', 'description': 'Comida y bebida'},
    {'name': 'Salones de Belleza', 'slug': 'salones-de-belleza', 'icon': 'scissors', 'description': 'Cuidado personal'},
    {'name': 'Talleres Mecanicos', 'slug': 'talleres-mecanicos', 'icon': 'wrench', 'description': 'Reparacion de vehiculos'},
    {'name': 'Clinicas', 'slug': 'clinicas', 'icon': 'hospital', 'description': 'Servicios de salud'},
    {'name': 'Tiendas', 'slug': 'tiendas', 'icon': 'store', 'description': 'Venta de productos'},
    {'name': 'Gimnasios', 'slug': 'gimnasios', 'icon': 'dumbbell', 'description': 'Fitness y deporte'},
    {'name': 'Escuelas', 'slug': 'escuelas', 'icon': 'book', 'description': 'Educacion'},
    {'name': 'Hoteles', 'slug': 'hoteles', 'icon': 'hotel', 'description': 'Hospedaje'},
    {'name': 'Servicios Profesionales', 'slug': 'servicios-profesionales', 'icon': 'briefcase', 'description': 'Abogados, contadores, etc.'},
    {'name': 'Tecnologia', 'slug': 'tecnologia', 'icon': 'laptop', 'description': 'Servicios de IT y tecnologia'},
]
for data in categories:
    obj, created = Category.objects.get_or_create(slug=data['slug'], defaults=data)
    status = 'CREADO' if created else 'YA EXISTIA'
    print(f"  {status}: {obj.name}")

print(f"\nSeed completado!")
print(f"  - PublicationStatus: {PublicationStatus.objects.count()}")
print(f"  - OperationalStatus: {OperationalStatus.objects.count()}")
print(f"  - Categories: {Category.objects.count()}")
