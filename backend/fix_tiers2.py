import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

# 1 large, 1 medium, rest small
updates = {
    'Restaurante La Cosecha': 'large',    # keep 1 large
    'Pizzeria Don Mario': 'small',         # was large → small
    'Academia Futuro Brillante': 'medium', # keep 1 medium
    'Veterinaria Patitas Felices': 'small',# was medium → small
    'Peluqueria Glamour': 'small',         # was medium → small
}

for biz in Business.objects.filter(is_featured=True):
    new_tier = updates.get(biz.name)
    if new_tier and biz.featured_tier != new_tier:
        old = biz.featured_tier
        biz.featured_tier = new_tier
        biz.save(update_fields=['featured_tier'])
        print(f"  {biz.name}: {old} -> {new_tier}")

print("\nResultado:")
for tier in ['large', 'medium', 'small']:
    names = list(Business.objects.filter(is_featured=True, featured_tier=tier).values_list('name', flat=True))
    print(f"  {tier}: {len(names)} -> {names}")
