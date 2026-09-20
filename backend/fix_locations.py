import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business
from business_locations.models import BusinessLocation

# Coordinates for Moca and nearby areas
moca_center = (19.3934, -70.5241)

# All municipalities in/near Espaillat
locations = [
    # Moca
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
    # Gaspar Hernandez
    (19.6334, -70.2667, 'Gaspar Hernández', 'Gaspar Hernández', 'Espaillat'),
    (19.6300, -70.2700, 'Gaspar Hernández', 'Gaspar Hernández', 'Espaillat'),
    (19.6350, -70.2640, 'Gaspar Hernández', 'Gaspar Hernández', 'Espaillat'),
    # Jamao al Norte
    (19.6334, -70.4667, 'Jamao al Norte', 'Jamao al Norte', 'Espaillat'),
    (19.6300, -70.4700, 'Jamao al Norte', 'Jamao al Norte', 'Espaillat'),
    # San Víctor
    (19.4667, -70.5333, 'San Víctor', 'San Víctor', 'Espaillat'),
    (19.4650, -70.5350, 'San Víctor', 'San Víctor', 'Espaillat'),
    # Cayetano Germosén
    (19.4000, -70.5167, 'Cayetano Germosén', 'Cayetano Germosén', 'Espaillat'),
    (19.3980, -70.5180, 'Cayetano Germosén', 'Cayetano Germosén', 'Espaillat'),
    # La Vega (nearby)
    (19.2211, -70.5297, 'La Vega', 'La Vega', 'La Vega'),
    (19.2200, -70.5310, 'La Vega', 'La Vega', 'La Vega'),
    # Salcedo
    (19.3833, -70.4167, 'Salcedo', 'Salcedo', 'Hermanas Mirabal'),
    (19.3820, -70.4180, 'Salcedo', 'Salcedo', 'Hermanas Mirabal'),
    # Castillo
    (19.3167, -70.5500, 'Castillo', 'Castillo', 'Duarte'),
    (19.3150, -70.5520, 'Castillo', 'Castillo', 'Duarte'),
    # Additional Moca locations
    (19.3940, -70.5245, 'Moca', 'Moca', 'Espaillat'),
    (19.3915, -70.5235, 'Moca', 'Moca', 'Espaillat'),
    (19.3975, -70.5215, 'Moca', 'Moca', 'Espaillat'),
    (19.3895, -70.5250, 'Moca', 'Moca', 'Espaillat'),
    (19.3965, -70.5265, 'Moca', 'Moca', 'Espaillat'),
    (19.3935, -70.5195, 'Moca', 'Moca', 'Espaillat'),
    (19.3905, -70.5225, 'Moca', 'Moca', 'Espaillat'),
    (19.3955, -70.5275, 'Moca', 'Moca', 'Espaillat'),
    (19.3925, -70.5185, 'Moca', 'Moca', 'Espaillat'),
    (19.3985, -70.5240, 'Moca', 'Moca', 'Espaillat'),
    (19.3880, -70.5210, 'Moca', 'Moca', 'Espaillat'),
    (19.3948, -70.5230, 'Moca', 'Moca', 'Espaillat'),
    (19.3912, -70.5260, 'Moca', 'Moca', 'Espaillat'),
]

# Streets in Moca
streets = [
    'Av. Duarte #123',
    'Calle Mella #45',
    'Av. Independencia #200',
    'Calle María Teresa #67',
    'Av. 27 de Febrero #89',
    'Calle Las Américas #34',
    'Av. Juan Pablo Duarte #500',
    'Calle Restauración #12',
    'Av. Moca #78',
    'Calle Santiago #90',
    'Av. Principal #156',
    'Calle del Sol #23',
    'Av. Libertador #300',
    'Calle Paz #45',
    'Av. Central #67',
    'Calle Norte #89',
    'Av. Sur #123',
    'Calle Este #45',
    'Av. Oeste #67',
    'Calle Nueva #89',
    'Av. Antigua #123',
    'Calle Real #34',
    'Av. Nueva #56',
    'Calle Larga #78',
    'Av. Corta #90',
    'Calle Ancha #12',
    'Av. Angosta #34',
    'Calle Recta #56',
    'Av. Curva #78',
    'Calle Tortuosa #90',
    'Callejón del Sol #11',
    'Pasaje Luna #22',
    'Diagonal Central #33',
    'Transversal Norte #44',
    'Circular Sur #55',
]

sectors = [
    'Centro', 'Villa Progreso', 'Ensanche Moca', 'Villa Olímpica',
    'Los Jardines', 'Villa Verde', 'Colinas del Norte', 'Villa Real',
    'Sector Norte', 'Villa Nueva', 'Los Pinos', 'Jardín del Norte',
    'Villa Italia', 'Sector Sur', 'Villa Española', 'Los Maestros',
    'Villa Atenea', 'Sector Este', 'Villa Borinquen', 'Los Robles',
]

# Streets in other towns
streets_other = {
    'Gaspar Hernández': ['Av. Principal #100', 'Calle Central #45', 'Av. del Mar #67'],
    'Jamao al Norte': ['Calle Principal #23', 'Av. Norte #45'],
    'San Víctor': ['Av. San Víctor #56', 'Calle Nueva #78'],
    'Cayetano Germosén': ['Calle Central #12', 'Av. Germosén #34'],
    'La Vega': ['Av. 27 de Febrero #200', 'Calle Mella #90'],
    'Salcedo': ['Av. Salcedo #100', 'Calle Principal #45'],
    'Castillo': ['Calle Castillo #50', 'Av. del Castillo #67'],
}

import random
random.seed(42)

# Get all businesses (the 33 we just created, which are the latest ones)
biz_list = list(Business.objects.order_by('-id')[:33])
biz_list.reverse()  # oldest first among the new ones

for i, biz in enumerate(biz_list):
    loc = BusinessLocation.objects.filter(business=biz).first()
    if not loc:
        continue
    
    town_data = locations[i % len(locations)]
    lat, lng, municipality, town, province = town_data
    
    if municipality in streets_other:
        street = random.choice(streets_other[municipality])
    else:
        street = streets[i % len(streets)]
    
    sector = random.choice(sectors) if municipality == 'Moca' else town
    
    loc.street = street
    loc.sector = sector
    loc.municipality = municipality
    loc.province = province
    loc.latitude = lat
    loc.longitude = lng
    loc.save(update_fields=['street', 'sector', 'municipality', 'province', 'latitude', 'longitude'])
    
    print(f"  {biz.name} -> {municipality}, {province} ({lat}, {lng})")

print(f"\nUpdated {len(biz_list)} businesses to Moca/Espaillat area")
