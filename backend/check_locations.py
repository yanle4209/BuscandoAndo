import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from business_locations.models import BusinessLocation

provinces = {}
for loc in BusinessLocation.objects.all():
    prov = loc.province or 'N/A'
    if prov not in provinces:
        provinces[prov] = []
    provinces[prov].append(loc.business.name)

for prov, names in sorted(provinces.items()):
    print(f"\n{prov} ({len(names)}):")
    for n in names[:5]:
        print(f"  - {n}")
    if len(names) > 5:
        print(f"  ... y {len(names)-5} mas")
