import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from businesses.models import Business
from django.db.models import Count

# Find duplicates by name
duplicates = Business.objects.values('name').annotate(cnt=Count('id')).filter(cnt__gt=1)
for d in duplicates:
    name = d['name']
    dupes = Business.objects.filter(name=name).order_by('id')
    keep = dupes.first()
    to_delete = dupes.exclude(pk=keep.pk)
    count = to_delete.count()
    to_delete.delete()
    print("  Deleted {} duplicate(s) of '{}'".format(count, name))

# Now feature only 5
Business.objects.filter(is_featured=True).update(is_featured=False, featured_permanent=False, featured_tier=None)

first_five = Business.objects.order_by('id')[:5]
levels = ['1', '2', '3', '4', '1']
for i, biz in enumerate(first_five):
    biz.is_featured = True
    biz.featured_permanent = True
    biz.featured_tier = levels[i]
    biz.save()
    print("  Nivel {}: {}".format(levels[i], biz.name))

print("\nTotal businesses: {}".format(Business.objects.count()))
print("Featured: {}".format(Business.objects.filter(is_featured=True).count()))
