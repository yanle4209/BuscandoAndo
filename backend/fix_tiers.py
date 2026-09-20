import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from businesses.models import Business

# Fix the ones that didn't match due to encoding
for biz in Business.objects.filter(is_featured=True):
    if 'Don Mario' in biz.name:
        biz.featured_tier = 'large'
        biz.save(update_fields=['featured_tier'])
        print(f"Fixed: {biz.name} -> large")
    elif 'Glamour' in biz.name:
        biz.featured_tier = 'medium'
        biz.save(update_fields=['featured_tier'])
        print(f"Fixed: {biz.name} -> medium")

print("\nAll tiers:")
for biz in Business.objects.filter(is_featured=True):
    print(f"  {biz.name}: {biz.featured_tier}")
