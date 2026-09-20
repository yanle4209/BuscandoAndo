import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business

for biz in Business.objects.filter(is_featured=True).order_by('featured_tier', 'name'):
    print(f"  [{biz.featured_tier}] {biz.name}")
