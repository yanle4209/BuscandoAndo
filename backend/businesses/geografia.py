"""El mapa: donde cae cada punto y a que distancia esta de un municipio.

Aqui viven el radio de R1 y las cabeceras de la seccion 9, que son las dos
cosas con que miden las demas piezas:

* ``views`` recorta con ellas la busqueda a 5 km del punto activo;
* ``validacion`` comprueba con ellas que un dato que llega cae dentro del
  municipio que dice ser;
* el importador de OSM centra con ellas la consulta y reparte cada
  candidato por su municipio.

Antes estaban todas en ``views``: al meter el importador se creaba un
ciclo de imports (``views`` -> ``validacion`` -> ``views``), asi que
pasan a su propio modulo. La vista ``cabeceras`` sigue en ``views``; aqui
esta solo el lector del CSV.
"""
import csv
import math
import unicodedata
from functools import lru_cache

from django.conf import settings
from django.db.models import Q

# Radio de busqueda en km. R1: las busquedas son unica y exclusivamente a
# 5 km del punto activo (la ubicacion del usuario; la cabecera municipal,
# si no la hay). Lo impone el backend: el cliente puede pedir menos, nunca
# mas. Ver DISENO.md R1.3.
RADIO_KM = 5.0

# Fuente estatica de las 158 cabeceras municipales (DISENO.md seccion 9).
CABECERAS_CSV = settings.BASE_DIR / 'data' / 'cabeceras_municipales.csv'

# Donde caen las fichas que no dicen a que municipio pertenecen. No se las
# esconde del reporte: no poder asignarlas es justo algo que hay que ver.
SIN_MUNICIPIO = '(sin municipio)'


def haversine_distance(lat1, lng1, lat2, lng2):
    """Calcular distancia en km entre dos puntos usando la formula de Haversine."""
    R = 6371  # Radio de la Tierra en km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def normalizar(texto):
    """Minusculas, sin acentos ni puntuacion, espacios juntos.

    La clave con la que se cruzan los nombres: "Baní" contra "Bani" es el
    mismo municipio, y "Café El Sol, SRL" contra "Cafe El Sol" es el mismo
    negocio (seccion 10-d: hay que cruzar ANTES de publicar).
    """
    texto = (texto or '').strip().casefold()
    texto = ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
    )
    texto = ''.join(
        caracter if caracter.isalnum() else ' ' for caracter in texto
    )
    return ' '.join(texto.split())


@lru_cache(maxsize=1)
def cabeceras():
    """Las cabeceras municipales del pais, leidas una sola vez del CSV.

    El archivo ``backend/data/cabeceras_municipales.csv`` (DISENO.md
    seccion 9) es una fuente estatica: municipio + provincia de Wikipedia,
    cruzada con OpenStreetMap en este orden: ``amenity=townhall`` ->
    ``office=government`` -> nodo ``place=*`` -> centroide. Se descarta
    cualquier punto a mas de 30 km del centroide del poligono.

    149 de los 158 apuntan al pueblo; los 9 restantes al centroide del
    municipio. Se cachea para no releer el disco en cada llamada.
    """
    if not CABECERAS_CSV.exists():
        return []
    with CABECERAS_CSV.open(encoding='utf-8') as fh:
        filas = csv.DictReader(fh)
        return [
            {
                'provincia': (fila.get('provincia') or '').strip(),
                'municipio': (fila.get('municipio') or '').strip(),
                'lat': float(fila['lat']),
                'lng': float(fila['lng']),
            }
            for fila in filas
            if (fila.get('lat') or '').strip() and (fila.get('lng') or '').strip()
        ]


def cabecera_para(municipio, provincia=None):
    """La cabecera del municipio en el CSV, o ``None`` si no aparece.

    Desempate por provincia: primero nombre + provincia (dos municipios
    homonimos no deberian cruzarse) y, si no coincide, el primer municipio
    con ese nombre.
    """
    clave = normalizar(municipio)
    if not clave:
        return None
    provincia_clave = normalizar(provincia)

    por_nombre = None
    for cab in cabeceras():
        if normalizar(cab['municipio']) != clave:
            continue
        if provincia_clave and normalizar(cab['provincia']) == provincia_clave:
            return cab
        por_nombre = por_nombre or cab
    return por_nombre


def cabecera_mas_cercana(lat, lng, radio_km):
    """La cabecera de la que esta a ``radio_km`` o menos, o ``None``.

    Es como se reparte un candidato de OSM entre municipios: con el radio
    por defecto los circulos de dos cabeceras vecinas no se pisan, y el
    que mas cerca este se queda con el. Si no hay ninguna dentro, el
    candidato queda fuera — es lo que dice §10: "importar lejos del centro
    no entra en ningun circulo".
    """
    mejor = None
    mejor_distancia = radio_km
    for cab in cabeceras():
        distancia = haversine_distance(lat, lng, cab['lat'], cab['lng'])
        if distancia <= mejor_distancia:
            mejor, mejor_distancia = cab, distancia
    return mejor


# ---------------------------------------------------------------------------
# Fase geografica (DISENO.md FASE1).
#
# El proyecto abre por PROVINCIAS — hoy Espaillat, Santiago, La Vega y
# Hermanas Mirabal — y la lista crece provincia a provincia. La fase NO
# borra nada: recorta vistas (listado, destacados, cabeceras) y las
# fichas de fuera siguen abriéndose por enlace directo. Sin provincias
# configuradas (tupla vacia) no hay fase: entra todo, que es el estado
# anterior y la forma de volver atras en un deploy.
# ---------------------------------------------------------------------------

def _fase_claves():
    """Las provincias de fase normalizadas (minusculas, sin tildes).

    Sin cache: se lee ``settings`` en cada llamada para que
    ``override_settings`` de los tests (y un deploy que cambie la
    tupla) mande de verdad. El coste es normalizar cuatro nombres.
    """
    return tuple(
        normalizar(p) for p in settings.FASE1_PROVINCIAS if p.strip()
    )


def q_fase():
    """El filtro de fase geografica para los LISTADOS (DISENO.md FASE1).

    Solo recorta lo que se enseña: las fichas fuera de fase siguen en la
    base y se abren por enlace directo (retrieve no pasa por aqui). El
    province del location es texto libre, asi que se compara sin
    distinguir mayusculas — las cuatro provincias actuales no tienen
    tildes. Una ficha SIN fila de ubicacion no puede decirse de donde
    es, asi que tampoco sale en el listado (el admin la sigue viendo).
    Sin ``FASE1_PROVINCIAS`` no se recorta nada (y volver a ponerlo es
    un solo deploy).

    Vive aqui (y no en ``views``) porque la usan el listado, los
    destacados Y el sitemap: todos tienen que recortar igual.
    """
    nombres = settings.FASE1_PROVINCIAS
    if not nombres:
        return Q()
    q = Q()
    for nombre in nombres:
        q |= Q(location__province__iexact=nombre)
    return q


def en_fase(provincia):
    """¿La provincia (texto libre de la base) esta en la fase actual?

    Sin fase configurada entra todo; con fase, se compara normalizado
    porque el campo es texto libre ("Santiago" vs "santiago ").
    """
    claves = _fase_claves()
    if not claves:
        return True
    return normalizar(provincia) in claves


def cabeceras_en_fase():
    """Las cabeceras municipales de las provincias de fase.

    El padron COMPLETO (158) sigue en ``cabeceras()``: lo usan el admin,
    el importador y el reporte de pendientes. Esto es solo lo que se le
    enseña al publico.
    """
    claves = _fase_claves()
    if not claves:
        return cabeceras()
    return [c for c in cabeceras() if normalizar(c['provincia']) in claves]


def punto_en_fase(lat, lng, radio_km=None):
    """¿El punto cae a ``radio_km`` o menos de una cabecera de FASE?

    Sin radio ilimitado: la pregunta es "¿este punto tiene municipio de
    fase cerca?", no "¿está dentro del circulo de busqueda?". Por eso el
    default es el doble del radio de lugar de las metricas (15 km): un
    vecino a 10 km del centro del pueblo sigue siendo del pueblo.
    """
    if radio_km is None:
        radio_km = 2 * 15.0
    claves = _fase_claves()
    if not claves:
        return True
    for cab in cabeceras():
        if normalizar(cab['provincia']) not in claves:
            continue
        if haversine_distance(lat, lng, cab['lat'], cab['lng']) <= radio_km:
            return True
    return False
