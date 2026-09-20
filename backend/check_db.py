import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus
from categories.models import Category
from businesses.models import Business

print("=== Publication Statuses ===")
for ps in PublicationStatus.objects.all():
    print(f"  [{ps.id}] {ps.name} (slug: {ps.slug})")

print("\n=== Operational Statuses ===")
for os2 in OperationalStatus.objects.all():
    print(f"  [{os2.id}] {os2.name} (slug: {os2.slug})")

print("\n=== Categories ===")
for cat in Category.objects.all():
    print(f"  [{cat.id}] {cat.name}")

print(f"\n=== Businesses: {Business.objects.count()} ===")
for b in Business.objects.all().order_by('name'):
    print(f"  [{b.id}] {b.name} | cat_id:{b.category_id} | pub:{b.publication_status_id} | op:{b.operational_status_id}")
