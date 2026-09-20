import os, django, random
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from business_locations.models import BusinessLocation

random.seed(77)

moca_coords = [
    (19.3934, -70.5241), (19.3980, -70.5200), (19.3900, -70.5300),
    (19.3950, -70.5180), (19.3920, -70.5260), (19.3960, -70.5220),
    (19.3890, -70.5190), (19.3970, -70.5280), (19.3910, -70.5210),
    (19.3945, -70.5255), (19.3870, -70.5230), (19.3990, -70.5170),
    (19.3885, -70.5270), (19.3955, -70.5150), (19.3930, -70.5310),
    (19.3940, -70.5245), (19.3915, -70.5235), (19.3975, -70.5215),
    (19.3895, -70.5250), (19.3965, -70.5265), (19.3935, -70.5195),
    (19.3905, -70.5225), (19.3955, -70.5275), (19.3925, -70.5185),
]

i = 0
for loc in BusinessLocation.objects.all():
    lat, lng = moca_coords[i % len(moca_coords)]
    loc.municipality = 'Moca'
    loc.province = 'Espaillat'
    loc.latitude = lat
    loc.longitude = lng
    loc.save(update_fields=['municipality', 'province', 'latitude', 'longitude'])
    print(f"  {loc.business.name} -> Moca")
    i += 1

print(f"\nTotal: {i} negocios en Moca")
