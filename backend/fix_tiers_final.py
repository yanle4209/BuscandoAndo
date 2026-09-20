import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

# Need: 1 large + 1 medium + 7 small per page = 9 per page
# With 18 featured: need 2 large, 2 medium, 14 small

# Promote 1 small to large
promote_to_large = [
    'Pizzeria Don Mario',
    'Pizzer\u00f3a Don Mario',
]
promote_to_medium = [
    'Veterinaria Patitas Felices',
]

for biz in Business.objects.filter(is_featured=True):
    for name in promote_to_large:
        if biz.name == name or biz.name.startswith('Pizzer'):
            biz.featured_tier = 'large'
            biz.save(update_fields=['featured_tier'])
            print(f"  {biz.name} -> large")
            break
    for name in promote_to_medium:
        if biz.name == name or biz.name.startswith('Veterinaria Patitas'):
            biz.featured_tier = 'medium'
            biz.save(update_fields=['featured_tier'])
            print(f"  {biz.name} -> medium")
            break

print("\nFinal distribution:")
for tier in ['large', 'medium', 'small']:
    names = list(Business.objects.filter(is_featured=True, featured_tier=tier).values_list('name', flat=True))
    print(f"  {tier}: {len(names)}")
    for n in names:
        print(f"    - {n}")
print(f"\nPages needed: 2 (9 + 9)")
