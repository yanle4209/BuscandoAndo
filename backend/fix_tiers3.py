import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

# Keep La Cosecha as large, Academia as medium, rest small
keep_large = 'Restaurante La Cosecha'
keep_medium = 'Academia Futuro Brillante'

for biz in Business.objects.filter(is_featured=True):
    if biz.name == keep_large:
        new_tier = 'large'
    elif biz.name == keep_medium:
        new_tier = 'medium'
    else:
        new_tier = 'small'
    
    if biz.featured_tier != new_tier:
        old = biz.featured_tier
        biz.featured_tier = new_tier
        biz.save(update_fields=['featured_tier'])
        print(f"  CHANGED: {biz.name}: {old} -> {new_tier}")
    else:
        print(f"  OK: {biz.name}: {biz.featured_tier}")

print("\nFinal distribution:")
for tier in ['large', 'medium', 'small']:
    names = list(Business.objects.filter(is_featured=True, featured_tier=tier).values_list('name', flat=True))
    print(f"  {tier}: {len(names)} -> {names}")
