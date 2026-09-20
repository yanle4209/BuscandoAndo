import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

qs = Business.objects.filter(is_featured=True)
print(f"Total featured: {qs.count()}")
for b in qs:
    print(f"  [{b.featured_tier or 'sin tier'}] {b.name}")
