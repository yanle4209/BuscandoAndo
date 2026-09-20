import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

# Assign tiers to the 10 new featured that have no tier
# Keep existing 1 large + 1 medium + 6 small
# New ones: alternate medium and small
no_tier = Business.objects.filter(is_featured=True, featured_tier__isnull=True)
count = 0
for biz in no_tier:
    count += 1
    if count <= 2:
        biz.featured_tier = 'medium'
    else:
        biz.featured_tier = 'small'
    biz.save(update_fields=['featured_tier'])
    print(f"  {biz.name} -> {biz.featured_tier}")

# Final distribution
print("\nFinal:")
for tier in ['large', 'medium', 'small']:
    names = list(Business.objects.filter(is_featured=True, featured_tier=tier).values_list('name', flat=True))
    print(f"  {tier}: {len(names)} -> {names}")
