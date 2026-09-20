"""
Importar negocios reales de Moca desde OpenStreetMap (Overpass API).
Centro: Juan Lopez, Moca, Espaillat (19.39, -70.52)
Radio: 10 km
"""
import os, django, json, urllib.request, urllib.parse, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from django.utils.text import slugify
from businesses.models import Business
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from categories.models import Category
from datetime import time as dt_time

# Centro: Juan Lopez, Moca
CENTER_LAT = 19.39
CENTER_LNG = -70.52
RADIUS = 10000  # 10 km

# Categorias de OSM -> Nuestras categorias
OSM_CATEGORY_MAP = {
    # Restaurantes
    'restaurant': 'Restaurantes',
    'fast_food': 'Restaurantes',
    'cafe': 'Restaurantes',
    'bar': 'Restaurantes',
    'pub': 'Restaurantes',
    'ice_cream': 'Restaurantes',
    # Tiendas
    'supermarket': 'Tiendas',
    'convenience': 'Tiendas',
    'clothes': 'Tiendas',
    'shoes': 'Tiendas',
    'electronics': 'Tiendas',
    'hardware': 'Tiendas',
    'furniture': 'Tiendas',
    'jewelry': 'Tiendas',
    'kiosk': 'Tiendas',
    'mall': 'Tiendas',
    'department_store': 'Tiendas',
    'florist': 'Tiendas',
    'bakery': 'Tiendas',
    'butcher': 'Tiendas',
    'greengrocer': 'Tiendas',
    'chemist': 'Tiendas',
    'pharmacy': 'Tiendas',
    'optician': 'Tiendas',
    # Salones
    'hairdresser': 'Salones de Belleza',
    'beauty_salon': 'Salones de Belleza',
    'nail_salon': 'Salones de Belleza',
    'tattoo': 'Salones de Belleza',
    # Servicios
    'bank': 'Servicios',
    'bureau_de_change': 'Servicios',
    'money_lender': 'Servicios',
    'post_office': 'Servicios',
    'car_rental': 'Servicios',
    'car_wash': 'Servicios',
    'car_repair': 'Servicios',
    'fuel': 'Servicios',
    'hotel': 'Servicios',
    'motel': 'Servicios',
    'hostel': 'Servicios',
    # Salud
    'hospital': 'Salud',
    'clinic': 'Salud',
    'doctors': 'Salud',
    'dentist': 'Salud',
    'veterinary': 'Salud',
    # Educacion
    'school': 'Educacion',
    'university': 'Educacion',
    'college': 'Educacion',
    'kindergarten': 'Educacion',
    'language_school': 'Educacion',
    'music_school': 'Educacion',
    # Deporte
    'gym': 'Deporte',
    'fitness_centre': 'Deporte',
    'sports_centre': 'Deporte',
    'stadium': 'Deporte',
    # Otros
    'marketplace': 'Otros',
    'chemist': 'Otros',
}

# Busquedas Overpass por tipo
OVERPASS_QUERIES = [
    # Restaurantes y comida
    f'[out:json][timeout:30];area[name="Moca"]->.searchArea;(node["amenity"~"restaurant|fast_food|cafe|bar|pub|ice_cream"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["amenity"~"restaurant|fast_food|cafe|bar|pub|ice_cream"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
    # Tiendas
    f'[out:json][timeout:30];(node["shop"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["shop"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
    # Servicios (bancos, carros, hoteles)
    f'[out:json][timeout:30];(node["amenity"~"bank|bureau_de_change|car_rental|car_wash|car_repair|fuel|hotel|motel|hostel|post_office"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["amenity"~"bank|bureau_de_change|car_rental|car_wash|car_repair|fuel|hotel|motel|hostel|post_office"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
    # Salones de belleza
    f'[out:json][timeout:30];(node["shop"~"hairdresser|beauty|nail_salon"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["shop"~"hairdresser|beauty|nail_salon"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
    # Salud
    f'[out:json][timeout:30];(node["amenity"~"hospital|clinic|doctors|dentist|veterinary|pharmacy"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["amenity"~"hospital|clinic|doctors|dentist|veterinary|pharmacy"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
    # Educacion
    f'[out:json][timeout:30];(node["amenity"~"school|university|college|kindergarten|language_school|music_school"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["amenity"~"school|university|college|kindergarten|language_school|music_school"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
    # Deporte y otros
    f'[out:json][timeout:30];(node["leisure"~"fitness_centre|sports_centre|stadium|gym"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});way["leisure"~"fitness_centre|sports_centre|stadium|gym"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG});node["amenity"~"marketplace"](around:{RADIUS},{CENTER_LAT},{CENTER_LNG}););out center;',
]

# Defaults
DEFAULT_CATEGORY = 'Otros'
pub_publicado_id = 2
op_abierto_id = 1

def get_or_create_category(name):
    slug = slugify(name, allow_unicode=True)
    cat, _ = Category.objects.get_or_create(name=name, defaults={'slug': slug})
    return cat

def parse_hours(tags):
    """Parse OSM opening_hours string to our format."""
    hours = []
    if not tags.get('opening_hours'):
        return hours
    
    oh = tags['opening_hours']
    day_map = {
        'Mo': 'Lunes', 'Tu': 'Martes', 'We': 'Miercoles',
        'Th': 'Jueves', 'Fr': 'Viernes', 'Sa': 'Sabado', 'Su': 'Domingo'
    }
    all_days = list(day_map.keys())
    
    try:
        # Simple parser for common formats like "Mo-Fr 08:00-17:00; Sa 09:00-12:00"
        parts = oh.replace(' ', '').split(';')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Extract time range
            time_range = None
            for token in part.split():
                if ':' in token and '-' in token:
                    time_range = token
                    break
            
            if not time_range:
                continue
            
            times = time_range.split('-')
            if len(times) != 2:
                continue
            
            open_t = dt_time.fromisoformat(times[0][:5])
            close_t = dt_time.fromisoformat(times[1][:5])
            
            # Extract days
            day_part = part.replace(time_range, '').strip()
            if not day_part:
                # Apply to all days
                for eng, esp in day_map.items():
                    hours.append({'day': esp, 'open': open_t, 'close': close_t})
                continue
            
            # Parse day ranges
            if '-' in day_part:
                start_day, end_day = day_part.split('-')
                if start_day in day_map and end_day in day_map:
                    start_idx = all_days.index(start_day)
                    end_idx = all_days.index(end_day)
                    for i in range(start_idx, end_idx + 1):
                        hours.append({'day': day_map[all_days[i]], 'open': open_t, 'close': close_t})
            elif ',' in day_part:
                for d in day_part.split(','):
                    d = d.strip()
                    if d in day_map:
                        hours.append({'day': day_map[d], 'open': open_t, 'close': close_t})
            elif day_part in day_map:
                hours.append({'day': day_map[day_part], 'open': open_t, 'close': close_t})
    except Exception:
        pass
    
    return hours

def fetch_overpass(query):
    """Fetch data from Overpass API (using mail.ru mirror)."""
    url = 'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"  Error en Overpass: {e}")
        return None

def get_lat_lng(element):
    """Get lat/lng from element (node or way)."""
    if element['type'] == 'node':
        return element.get('lat'), element.get('lon')
    elif element.get('center'):
        return element['center'].get('lat'), element['center'].get('lon')
    return None, None

def clean_name(name):
    """Clean OSM name."""
    if not name:
        return None
    name = name.strip()
    # Remove common prefixes/suffixes that are redundant
    for prefix in ['Restaurant ', 'Restaurante ', 'Tienda ', 'Peluqueria ', 'Farmacia ']:
        if name.startswith(prefix) and len(name) > len(prefix):
            pass  # Keep as is, might be part of the name
    return name if len(name) > 1 else None

def import_from_osm():
    """Main import function."""
    created = 0
    skipped = 0
    seen_names = set()
    
    categories = {}
    for cat_name in set(OSM_CATEGORY_MAP.values()):
        categories[cat_name] = get_or_create_category(cat_name)
    
    print(f"Categorias creadas: {len(categories)}")
    print(f"Buscando negocios en {RADIUS/1000}km de Moca...")
    print()
    
    for i, query in enumerate(OVERPASS_QUERIES):
        print(f"Consulta {i+1}/{len(OVERPASS_QUERIES)}...")
        result = fetch_overpass(query)
        if not result:
            continue
        
        elements = result.get('elements', [])
        print(f"  {len(elements)} elementos encontrados")
        
        for elem in elements:
            tags = elem.get('tags', {})
            name = clean_name(tags.get('name'))
            if not name:
                skipped += 1
                continue
            
            # Dedup by name
            name_lower = name.lower().strip()
            if name_lower in seen_names:
                skipped += 1
                continue
            seen_names.add(name_lower)
            
            lat, lng = get_lat_lng(elem)
            if not lat or not lng:
                skipped += 1
                continue
            
            # Determine category
            amenity = tags.get('amenity', '')
            shop = tags.get('shop', '')
            leisure = tags.get('leisure', '')
            
            osm_type = amenity or shop or leisure
            cat_name = OSM_CATEGORY_MAP.get(osm_type, DEFAULT_CATEGORY)
            category = categories.get(cat_name, categories[DEFAULT_CATEGORY])
            
            # Create slug
            slug = slugify(name, allow_unicode=True)
            base_slug = slug
            counter = 1
            while Business.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Description
            description = tags.get('description', '')
            if not description:
                desc_parts = []
                if tags.get('cuisine'):
                    desc_parts.append(f"Cocina: {tags['cuisine']}")
                if tags.get('brand'):
                    desc_parts.append(f"Marca: {tags['brand']}")
                if tags.get('operator'):
                    desc_parts.append(f"Operador: {tags['operator']}")
                description = '. '.join(desc_parts) if desc_parts else f"Negocio en Moca, Espaillat."
            
            short_desc = tags.get('description', '')[:300] if tags.get('description') else ''
            
            # Phone
            phone = tags.get('phone', tags.get('contact:phone', ''))
            
            # Email
            email = tags.get('email', tags.get('contact:email', ''))
            
            # Website
            website = tags.get('website', tags.get('contact:website', ''))
            
            # Street address
            street = tags.get('addr:street', '')
            number = tags.get('addr:housenumber', '')
            if street and number:
                street = f"{street} #{number}"
            elif not street:
                street = tags.get('addr:full', '')
            
            sector = tags.get('addr:suburb', tags.get('addr:neighbourhood', ''))
            
            # Create business
            biz = Business.objects.create(
                name=name,
                slug=slug,
                description=description,
                short_description=short_desc,
                category=category,
                publication_status_id=pub_publicado_id,
                operational_status_id=op_abierto_id,
                is_featured=False,
            )
            
            # Location
            BusinessLocation.objects.create(
                business=biz,
                street=street,
                sector=sector,
                municipality='Moca',
                province='Espaillat',
                latitude=lat,
                longitude=lng,
            )
            
            # Contact
            if phone or email:
                BusinessContact.objects.create(
                    business=biz,
                    phone=phone,
                    email=email,
                )
            
            # Hours
            hours = parse_hours(tags)
            if hours:
                for h in hours:
                    BusinessHours.objects.create(
                        business=biz,
                        day=h['day'],
                        open_time=h['open'],
                        close_time=h['close'],
                        is_closed=False,
                    )
            
            created += 1
            if created % 10 == 0:
                print(f"  [{created}] {name} ({cat_name})")
        
        # Be polite to Overpass API
        time.sleep(2)
    
    print(f"\n{'='*50}")
    print(f"RESULTADO:")
    print(f"  Creados: {created}")
    print(f"  Omitidos: {skipped}")
    print(f"  Total en DB: {Business.objects.count()}")
    print(f"  Por categoria:")
    for cat in Category.objects.all():
        count = cat.businesses.count()
        if count > 0:
            print(f"    {cat.name}: {count}")

if __name__ == '__main__':
    import_from_osm()
