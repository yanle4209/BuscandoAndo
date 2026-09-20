import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

qs = Business.objects.filter(is_featured=True)
print(f"Total destacados: {qs.count()}")
for tier in ['large', 'medium', 'small', None]:
    names = list(qs.filter(featured_tier=tier).values_list('name', flat=True))
    label = tier or 'sin tier'
    print(f"  {label}: {len(names)}")
    for n in names:
        print(f"    - {n}")
