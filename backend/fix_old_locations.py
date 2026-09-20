import os, django, random
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business
from business_locations.models import BusinessLocation

random.seed(99)

moca_locs = [
    (19.3934, -70.5241, 'Moca', 'Moca', 'Espaillat'),
    (19.3980, -70.5200, 'Moca', 'Moca', 'Espaillat'),
    (19.3900, -70.5300, 'Moca', 'Moca', 'Espaillat'),
    (19.3950, -70.5180, 'Moca', 'Moca', 'Espaillat'),
    (19.3920, -70.5260, 'Moca', 'Moca', 'Espaillat'),
    (19.3960, -70.5220, 'Moca', 'Moca', 'Espaillat'),
    (19.3890, -70.5190, 'Moca', 'Moca', 'Espaillat'),
    (19.3970, -70.5280, 'Moca', 'Moca', 'Espaillat'),
    (19.3910, -70.5210, 'Moca', 'Moca', 'Espaillat'),
    (19.3945, -70.5255, 'Moca', 'Moca', 'Espaillat'),
    (19.3870, -70.5230, 'Moca', 'Moca', 'Espaillat'),
    (19.3990, -70.5170, 'Moca', 'Moca', 'Espaillat'),
    (19.3885, -70.5270, 'Moca', 'Moca', 'Espaillat'),
    (19.3955, -70.5150, 'Moca', 'Moca', 'Espaillat'),
    (19.3930, -70.5310, 'Moca', 'Moca', 'Espaillat'),
    (19.3940, -70.5245, 'Moca', 'Moca', 'Espaillat'),
    (19.3915, -70.5235, 'Moca', 'Moca', 'Espaillat'),
    (19.3975, -70.5215, 'Moca', 'Moca', 'Espaillat'),
    (19.3895, -70.5250, 'Moca', 'Moca', 'Espaillat'),
    (19.3965, -70.5265, 'Moca', 'Moca', 'Espaillat'),
]

streets = [
    'Av. Duarte #123', 'Calle Mella #45', 'Av. Independencia #200',
    'Calle María Teresa #67', 'Av. 27 de Febrero #89', 'Calle Las Américas #34',
    'Av. Juan Pablo Duarte #500', 'Calle Restauración #12', 'Av. Moca #78',
    'Calle Santiago #90', 'Av. Principal #156', 'Calle del Sol #23',
    'Av. Libertador #300', 'Calle Paz #45', 'Av. Central #67',
    'Calle Norte #89', 'Av. Sur #123', 'Calle Este #45',
    'Av. Oeste #67', 'Calle Nueva #89',
]

sectors = [
    'Centro', 'Villa Progreso', 'Ensanche Moca', 'Villa Olímpica',
    'Los Jardines', 'Villa Verde', 'Colinas del Norte', 'Villa Real',
    'Sector Norte', 'Villa Nueva', 'Los Pinos', 'Jardín del Norte',
    'Villa Italia', 'Sector Sur', 'Villa Española', 'Los Maestros',
    'Villa Atenea', 'Sector Este', 'Villa Borinquen', 'Los Robles',
]

# Get ALL businesses not yet in Moca
all_biz = Business.objects.all()
updated = 0
for biz in all_biz:
    loc = BusinessLocation.objects.filter(business=biz).first()
    if not loc:
        continue
    # Skip if already in Moca/Espaillat area
    if loc.province in ['Espaillat', 'La Vega', 'Hermanas Mirabal', 'Duarte']:
        continue
    
    m = moca_locs[updated % len(moca_locs)]
    lat, lng, mun, town, prov = m
    
    loc.street = streets[updated % len(streets)]
    loc.sector = random.choice(sectors)
    loc.municipality = mun
    loc.province = prov
    loc.latitude = lat
    loc.longitude = lng
    loc.save(update_fields=['street', 'sector', 'municipality', 'province', 'latitude', 'longitude'])
    
    print(f"  {biz.name} -> Moca, Espaillat")
    updated += 1

print(f"\nUpdated {updated} old businesses to Moca")
print(f"Total businesses: {Business.objects.count()}")
