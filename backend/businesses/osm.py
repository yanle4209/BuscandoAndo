"""OpenStreetMap: traer los candidatos de un municipio y normalizarlos.

No decide nada. Solo dos cosas:

1. traer los elementos dentro del circulo de una cabecera, y
2. convertirlos al diccionario plano que entienden ``validar`` (¿se puede
   dejar entrar?) y, a partir de ahi, los constructores de ``Business``.

Que se publique, que se descarte por duplicado y a que municipio va es
cosa del importador y del canal de envio de §11.5 — que usan la misma
validacion.

Sustituye al ``backend/import_osm.py`` de una sola vez: aquel estaba
amarrado a Moca y a un radio de 10 km fijo, mientras que este trabaja por
cabecera y sobre el circulo de R1.
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import time as dt_time

from .validacion import limpiar_telefono

# Varios servidores, en orden: Overpass limita y a veces no contesta, y un
# municipio que no se puede consultar no deberia tumbar la corrida entera.
ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
]

USER_AGENT = 'BuscandoAndo-import/1.0'

AMENITIES = (
    'restaurant|fast_food|cafe|bar|pub|ice_cream|pharmacy|'
    'bank|bureau_de_change|car_rental|car_wash|car_repair|fuel|'
    'hotel|motel|hostel|post_office|'
    'hospital|clinic|doctors|dentist|veterinary|'
    'school|university|college|kindergarten|language_school|music_school|'
    'marketplace'
)

LEISURES = 'fitness_centre|sports_centre|stadium|gym'

# Etiqueta OSM -> nuestra categoria. Van a las del semillero
# (``load_initial_data``): si "gimnasio" esta en "Deporte" la busqueda no
# lo encuentra, porque el listado busca por ``category__name``.
OSM_CATEGORY_MAP = {
    # Restaurantes
    'restaurant': 'Restaurantes', 'fast_food': 'Restaurantes',
    'cafe': 'Restaurantes', 'bar': 'Restaurantes', 'pub': 'Restaurantes',
    'ice_cream': 'Restaurantes',
    # Tiendas
    'supermarket': 'Tiendas', 'convenience': 'Tiendas', 'clothes': 'Tiendas',
    'shoes': 'Tiendas', 'electronics': 'Tiendas', 'hardware': 'Tiendas',
    'furniture': 'Tiendas', 'jewelry': 'Tiendas', 'kiosk': 'Tiendas',
    'mall': 'Tiendas', 'department_store': 'Tiendas', 'florist': 'Tiendas',
    'bakery': 'Tiendas', 'butcher': 'Tiendas', 'greengrocer': 'Tiendas',
    'chemist': 'Tiendas', 'optician': 'Tiendas', 'toys': 'Tiendas',
    'sports': 'Tiendas', 'books': 'Tiendas', 'stationery': 'Tiendas',
    # Salones
    'hairdresser': 'Salones de Belleza', 'beauty': 'Salones de Belleza',
    'beauty_salon': 'Salones de Belleza', 'nail_salon': 'Salones de Belleza',
    'tattoo': 'Salones de Belleza',
    # Automocion
    'car_repair': 'Talleres Mecanicos',
    'car': 'Talleres Mecanicos', 'motorcycle': 'Talleres Mecanicos',
    # Salud
    'clinic': 'Clinicas', 'doctors': 'Clinicas', 'dentist': 'Clinicas',
    'hospital': 'Salud', 'veterinary': 'Salud', 'pharmacy': 'Salud',
    # Educacion
    'school': 'Escuelas', 'university': 'Escuelas', 'college': 'Escuelas',
    'kindergarten': 'Escuelas', 'language_school': 'Escuelas',
    'music_school': 'Escuelas',
    # Alojamiento
    'hotel': 'Hoteles', 'motel': 'Hoteles', 'hostel': 'Hoteles',
    'apartment': 'Hoteles', 'guest_house': 'Hoteles',
    # Deporte
    'gym': 'Gimnasios', 'fitness_centre': 'Gimnasios',
    'sports_centre': 'Deporte', 'stadium': 'Deporte', 'pitch': 'Deporte',
    # Servicios
    'bank': 'Servicios', 'bureau_de_change': 'Servicios',
    'car_rental': 'Servicios', 'car_wash': 'Servicios', 'fuel': 'Servicios',
    'post_office': 'Servicios', 'laundry': 'Servicios',
    # Otros
    'marketplace': 'Otros',
}

DEFAULT_CATEGORY = 'Otros'


def categoria_de(tags):
    """Nuestra categoria a partir de las etiquetas del elemento."""
    for clave in ('amenity', 'shop', 'leisure', 'tourism'):
        valor = tags.get(clave)
        if valor and valor in OSM_CATEGORY_MAP:
            return OSM_CATEGORY_MAP[valor]
    return DEFAULT_CATEGORY


def punto_de(elemento):
    """``(lat, lng)`` de un nodo, o el centro de una via. Si no, (None, None)."""
    if elemento.get('type') == 'node':
        return elemento.get('lat'), elemento.get('lon')
    centro = elemento.get('center') or {}
    return centro.get('lat'), centro.get('lon')


def calle_de(tags):
    """Calle y numero en el formato que espera ``BusinessLocation.street``."""
    calle = tags.get('addr:street', '')
    numero = tags.get('addr:housenumber', '')
    if calle and numero:
        return '%s #%s' % (calle, numero)
    if calle:
        return calle
    return tags.get('addr:full', '') or ''


def parse_hours(opening_hours):
    """El ``opening_hours`` de OSM a nuestras franjas por dia.

    Cubre lo comun (``Mo-Fr 08:00-17:00; Sa 09:00-12:00``). Lo que no se
    entienda se ignora entero en vez de inventar: un horario malo es peor
    que ningun horario.
    """
    horas = []
    if not opening_hours:
        return horas

    day_map = {
        'Mo': 'Lunes', 'Tu': 'Martes', 'We': 'Miercoles',
        'Th': 'Jueves', 'Fr': 'Viernes', 'Sa': 'Sabado', 'Su': 'Domingo',
    }
    todos = list(day_map.keys())

    try:
        for parte in str(opening_hours).replace(' ', '').split(';'):
            parte = parte.strip()
            if not parte:
                continue

            franja = next(
                (token for token in parte.split()
                 if ':' in token and '-' in token), None
            )
            if not franja:
                continue
            tiempos = franja.split('-')
            if len(tiempos) != 2:
                continue
            abre = dt_time.fromisoformat(tiempos[0][:5])
            cierra = dt_time.fromisoformat(tiempos[1][:5])

            dias = parte.replace(franja, '').strip()
            if not dias:
                for clave in day_map:
                    horas.append({'day': day_map[clave],
                                  'open': abre, 'close': cierra})
            elif '-' in dias:
                primero, ultimo = dias.split('-', 1)
                if primero in day_map and ultimo in day_map:
                    for i in range(todos.index(primero), todos.index(ultimo) + 1):
                        horas.append({'day': day_map[todos[i]],
                                      'open': abre, 'close': cierra})
            elif ',' in dias:
                for dia in dias.split(','):
                    if dia.strip() in day_map:
                        horas.append({'day': day_map[dia.strip()],
                                      'open': abre, 'close': cierra})
            elif dias in day_map:
                horas.append({'day': day_map[dias],
                              'open': abre, 'close': cierra})
    except Exception:
        return []

    return horas


def _consulta(cabecera, radio_km):
    """Una sola consulta Overpass por municipio, en vez de una por tipo.

    ``out center`` devuelve el centro de las vias, que es donde se
    coloca el pin.
    """
    centro = '%s,%s' % (cabecera['lat'], cabecera['lng'])
    radio = int(round(radio_km * 1000))
    trozos = []
    for etiqueta, valor in (
        ('amenity', AMENITIES),
        ('shop', ''),
        ('leisure', LEISURES),
        ('tourism', 'hotel|motel|hostel|guest_house'),
    ):
        condicion = ('"%s"~"%s"' % (etiqueta, valor) if valor
                     else '"%s"' % etiqueta)
        for tipo in ('node', 'way'):
            trozos.append('%s[%s](around:%d,%s);'
                          % (tipo, condicion, radio, centro))

    return (
        '[out:json][timeout:90];\n'
        '(\n%s\n);\nout center;' % '\n'.join(trozos)
    )


def consultar(cabecera, radio_km):
    """Los elementos dentro del circulo, o ``None`` si Overpass fallo.

    Se distingue ``None`` de ``[]``: uno es "no hubo red" y el otro es
    "este municipio no tiene nada en OSM". Mezclarlos haria creer que un
    municipio esta vacio cuando en realidad no se pudo consultar.
    """
    cuerpo = urllib.parse.urlencode(
        {'data': _consulta(cabecera, radio_km)}
    ).encode('utf-8')

    ultimo_error = None
    for url in ENDPOINTS:
        peticion = urllib.request.Request(url, data=cuerpo, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': USER_AGENT,
            'Accept': '*/*',
        })
        try:
            with urllib.request.urlopen(peticion, timeout=90) as respuesta:
                datos = json.loads(respuesta.read().decode('utf-8'))
            return datos.get('elements', [])
        except Exception as error:
            ultimo_error = error
    # Por stderr: el comando ya informa por stdout de que este municipio
    # no se pudo consultar, y aqui se ve el motivo concreto.
    sys.stderr.write('Overpass: %s\n' % ultimo_error)
    return None


def a_datos(elemento, cabecera):
    """El elemento de OSM al diccionario plano que validan los demas.

    El municipio y la provincia **salen de la cabecera**, nunca de las
    etiquetas del elemento: es lo que hace que el candidato quede
    asignado al circulo donde se busco.
    """
    tags = elemento.get('tags', {}) or {}
    lat, lng = punto_de(elemento)

    telefono = limpiar_telefono(
        tags.get('contact:phone') or tags.get('phone') or ''
    )
    correo = (tags.get('contact:email') or tags.get('email') or '').strip()
    web = (tags.get('contact:website') or tags.get('website') or '').strip()
    whatsapp = limpiar_telefono(
        tags.get('contact:whatsapp') or tags.get('whatsapp') or ''
    )

    return {
        'nombre': (tags.get('name') or '').strip(),
        'telefono': telefono,
        'whatsapp': whatsapp,
        'correo': correo,
        'web': web,
        'lat': lat,
        'lng': lng,
        'municipio': cabecera['municipio'],
        'provincia': cabecera['provincia'],
        'calle': calle_de(tags),
        'sector': (tags.get('addr:suburb')
                   or tags.get('addr:neighbourhood') or ''),
        'categoria': categoria_de(tags),
        'descripcion': _descripcion(tags),
        'horario': parse_hours(tags.get('opening_hours')),
        'cerrado': any(
            tags.get(clave) in ('yes', 'true')
            for clave in ('disused', 'abandoned', 'vacant', 'destroyed')
        ),
    }


def _descripcion(tags):
    """Descripcion corta a partir de lo que OSM si dice del negocio."""
    if tags.get('description'):
        return tags['description'][:300]

    partes = []
    if tags.get('cuisine'):
        partes.append('Cocina: %s' % tags['cuisine'])
    if tags.get('brand'):
        partes.append('Marca: %s' % tags['brand'])
    if tags.get('operator'):
        partes.append('Operador: %s' % tags['operator'])
    if tags.get('addr:city'):
        partes.append('En %s' % tags['addr:city'])
    return '. '.join(partes)
