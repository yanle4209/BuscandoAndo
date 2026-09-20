import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

qs = Business.objects.filter(is_featured=True)
print("Destacados por tier:")
for tier in ['large', 'medium', 'small', None]:
    count = qs.filter(featured_tier=tier).count()
    names = list(qs.filter(featured_tier=tier).values_list('name', flat=True))
    label = tier or 'sin tier'
    print(f"  {label}: {count}")
    for n in names:
        print(f"    - {n}")
print(f"\nTotal: {qs.count()}")
