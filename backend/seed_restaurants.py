import os, django, random
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from django.utils.text import slugify
from datetime import time as dt_time

random.seed(42)

pub_publicado_id = 2
op_abierto_id = 1
cat_restaurantes_id = 1

new_restaurants = [
    {
        'name': 'Restaurante La Casona',
        'description': 'Restaurante colonial con comida criolla, platos tipicos y ambiente familiar. Mojitos artesanales y musica en vivo los viernes.',
        'short_description': 'Comida criolla en ambiente colonial.',
        'phone': '809-555-3001', 'whatsapp': '8095553001', 'email': 'lacasona@gmail.com',
        'street': 'Calle Restauracion #78', 'sector': 'Centro',
        'lat': 19.3942, 'lng': -70.5250,
    },
    {
        'name': 'Comedor Doña Julia',
        'description': 'Comedor casero con la mejor comida del campo dominicano. Bandera dominicana, sancocho, habichuelas con gueduves.',
        'short_description': 'Comida casera dominicana.',
        'phone': '809-555-3002', 'whatsapp': '8095553002',
        'street': 'Av. Moca #234', 'sector': 'Villa Progreso',
        'lat': 19.3955, 'lng': -70.5220,
    },
    {
        'name': 'Taqueria El Mexicano',
        'description': 'Tacos, burritos, quesadillas y nachos con autentico sabor mexicano. Salsas picantes caseras.',
        'short_description': 'Sabor mexicano en Moca.',
        'phone': '809-555-3003', 'email': 'elmexicano@gmail.com',
        'street': 'Calle Santiago #45', 'sector': 'Ensanche Moca',
        'lat': 19.3920, 'lng': -70.5260,
    },
    {
        'name': 'Cafe Aroma del Norte',
        'description': 'Cafeteria artesanal con café dominicano de altura, reposteria fresca, desayunos y almuerzos ligeros.',
        'short_description': 'Café y reposteria artesanal.',
        'phone': '809-555-3004', 'email': 'aroma.norte@gmail.com',
        'street': 'Av. Juan Pablo Duarte #150', 'sector': 'Centro',
        'lat': 19.3938, 'lng': -70.5241,
    },
    {
        'name': 'Restaurante El Pescador',
        'description': 'Mariscos frescos del dia: pescado frito, camarones, pulpo a la plancha, ceviche y arroz con mariscos.',
        'short_description': 'Mariscos frescos del dia.',
        'phone': '809-555-3005', 'whatsapp': '8095553005',
        'street': 'Av. 27 de Febrero #89', 'sector': 'Villa Olímpica',
        'lat': 19.3910, 'lng': -70.5190,
    },
    {
        'name': 'Hamburgueseria The Burger Spot',
        'description': 'Hamburguesas artesanales con carne 100% res, papas caseras, onion rings y batidos naturales.',
        'short_description': 'Hamburguesas artesanales.',
        'phone': '809-555-3006', 'whatsapp': '8095553006',
        'street': 'Calle Las Americas #56', 'sector': 'Villa Nueva',
        'lat': 19.3965, 'lng': -70.5215,
    },
    {
        'name': 'Chifa Sol de China',
        'description': 'Restaurante chino con arroz chino, pollo agridulce, chofa, wantan frito y salsa agridulce.',
        'short_description': 'Comida china y oriental.',
        'phone': '809-555-3007', 'email': 'solchina@gmail.com',
        'street': 'Av. Libertador #67', 'sector': 'Centro',
        'lat': 19.3930, 'lng': -70.5235,
    },
    {
        'name': 'Donde Chepe - Asados',
        'description': 'Los mejores asados de la zona: pollo asado, chivo, cerdo, longaniza. Salsas criollas y tostones.',
        'short_description': 'Asados criollos al carbon.',
        'phone': '809-555-3008', 'whatsapp': '8095553008',
        'street': 'Av. Duarte #345', 'sector': 'Los Pinos',
        'lat': 19.3890, 'lng': -70.5270,
    },
    {
        'name': 'Ramen House Moca',
        'description': 'Ramen japonés autentico, gyoza, yakisoba y edamame. Caldos preparados por horas.',
        'short_description': 'Ramen y comida japonesa.',
        'phone': '809-555-3009', 'email': 'ramenmoca@gmail.com',
        'street': 'Calle Paz #23', 'sector': 'Ensanche Moca',
        'lat': 19.3948, 'lng': -70.5245,
    },
    {
        'name': 'Pasteleria Dulce Tentacion',
        'description': 'Pasteles personalizados, tortas, cupcakes, galletas y postres. Pedidos para eventos y cumpleanos.',
        'short_description': 'Pasteleria y postres.',
        'phone': '809-555-3010', 'whatsapp': '8095553010', 'email': 'dulcetentacion@gmail.com',
        'street': 'Calle Central #12', 'sector': 'Colinas del Norte',
        'lat': 19.3970, 'lng': -70.5280,
    },
    {
        'name': 'Comida Rapida El Primo',
        'description': 'Pollo frito, pernil, yuca frita, ensalada y arroz. Porciones grandes a precios accesibles.',
        'short_description': 'Comida rapida dominicana.',
        'phone': '809-555-3011',
        'street': 'Av. Sur #78', 'sector': 'Villa Real',
        'lat': 19.3905, 'lng': -70.5225,
    },
    {
        'name': 'Trattoria Italiana Bella Vista',
        'description': 'Pasta fresca hecha a mano, pizza napolitana, risotto y tiramisu. Vinos importados de Italia.',
        'short_description': 'Autentica cocina italiana.',
        'phone': '809-555-3012', 'email': 'bellavista.italiana@gmail.com',
        'street': 'Av. Abraham Lincoln #45', 'sector': 'Villa Italia',
        'lat': 19.3955, 'lng': -70.5150,
    },
    {
        'name': 'Jugo Bar Tropical',
        'description': 'Jugos naturales, batidos de frutas tropicales, acai bowls, smoothies y ensaladas frescas.',
        'short_description': 'Jugos y bowls saludables.',
        'phone': '809-555-3013', 'whatsapp': '8095553013',
        'street': 'Calle Nueva #34', 'sector': 'Villa Verde',
        'lat': 19.3935, 'lng': -70.5310,
    },
    {
        'name': 'Restaurante El Fogon',
        'description': 'Comida criolla al fogon de leña: mondongo, asopao, higado encebollado y mangú con los tres golpes.',
        'short_description': 'Comida al fogon de lena.',
        'phone': '809-555-3014', 'email': 'elfogon@gmail.com',
        'street': 'Calle Mella #123', 'sector': 'Sector Norte',
        'lat': 19.3980, 'lng': -70.5200,
    },
    {
        'name': 'Sabor Dominicano',
        'description': 'Restaurante de comida tipica con buffet dominicano. Morir soñando, morfeos, empanadas y jugos naturales.',
        'short_description': 'Buffet dominico completo.',
        'phone': '809-555-3015', 'whatsapp': '8095553015',
        'street': 'Av. Independencia #456', 'sector': 'Jardin del Norte',
        'lat': 19.3915, 'lng': -70.5235,
    },
]

moca_coords = [
    (19.3942, -70.5250), (19.3955, -70.5220), (19.3920, -70.5260),
    (19.3938, -70.5241), (19.3910, -70.5190), (19.3965, -70.5215),
    (19.3930, -70.5235), (19.3890, -70.5270), (19.3948, -70.5245),
    (19.3970, -70.5280), (19.3905, -70.5225), (19.3955, -70.5150),
    (19.3935, -70.5310), (19.3980, -70.5200), (19.3915, -70.5235),
]

sectors = [
    'Centro', 'Villa Progreso', 'Ensanche Moca', 'Villa Olímpica',
    'Los Jardines', 'Villa Verde', 'Colinas del Norte', 'Villa Real',
]

hours_restaurant = [
    ('Lunes', '11:00', '23:00', False),
    ('Martes', '11:00', '23:00', False),
    ('Miércoles', '11:00', '23:00', False),
    ('Jueves', '11:00', '23:00', False),
    ('Viernes', '11:00', '00:00', False),
    ('Sábado', '11:00', '00:00', False),
    ('Domingo', '11:00', '22:00', False),
]

created = 0
for i, data in enumerate(new_restaurants):
    name = data['name']
    slug = slugify(name, allow_unicode=True)
    base_slug = slug
    counter = 1
    while Business.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    biz = Business.objects.create(
        name=name,
        slug=slug,
        description=data['description'],
        short_description=data.get('short_description', ''),
        category_id=cat_restaurantes_id,
        publication_status_id=pub_publicado_id,
        operational_status_id=op_abierto_id,
        is_featured=False,
    )

    lat, lng = data['lat'], data['lng']
    BusinessLocation.objects.create(
        business=biz,
        street=data.get('street', ''),
        sector=data.get('sector', ''),
        municipality='Moca',
        province='Espaillat',
        latitude=lat,
        longitude=lng,
    )

    BusinessContact.objects.create(
        business=biz,
        phone=data.get('phone', ''),
        whatsapp=data.get('whatsapp', ''),
        email=data.get('email', ''),
    )

    for day_name, open_t, close_t, is_closed in hours_restaurant:
        open_time = dt_time.fromisoformat(open_t) if open_t else None
        close_time = dt_time.fromisoformat(close_t) if close_t else None
        BusinessHours.objects.create(
            business=biz,
            day=day_name,
            open_time=open_time,
            close_time=close_time,
            is_closed=is_closed,
        )

    created += 1
    print(f"  [{created:2d}] {name}")

print(f"\nCreated {created} restaurants")
print(f"Total businesses: {Business.objects.count()}")
print(f"Restaurantes category: {Business.objects.filter(category_id=cat_restaurantes_id).count()}")
