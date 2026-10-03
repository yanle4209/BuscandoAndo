"""El formato en que viajan las fichas de una base a otra (R5).

Ninguno de los dos comandos conoce al otro: ``exportar_fichas`` escribe
lo que aqui se define y ``cargar_fichas`` lo lee. El formato vive en un
tercer sitio a proposit — si viviera en el exportador, quien carga
tendria que copiarlo, y el dia que cambiara un campo los dos se
separarian sin que nadie lo viera.

No es un fixture de Django. ``dumpdata``/``loaddata`` trabajan con ids
primarios, y en la base de destino esos ids ya estan ocupados por otra
cosa: una categoria con id 5 aqui puede ser "Salud" y alla "Tiendas", con
lo que ``loaddata`` pisaria filas que no tocan. Aqui se viaja por
**nombre** —que es como ya cruza §10-d— y lo que llega se enriquece o se
crea, nunca se sobrescribe.

Un JSON por linea (JSONL), comprimido si el nombre acaba en ``.gz``:
linea a linea se puede leer sin cargar decenas de miles de fichas en
memoria a la vez.
"""
import gzip
import json
from datetime import time as dt_time

# Los mismos campos planos que producen ``osm.a_datos`` y
# ``levantamiento._a_datos``: quien recibe no distingue entre lo que vino
# de OpenStreetMap, lo que mando un colaborador y lo que se exporto de
# otra base, y por eso los tres pasan por la misma puerta y el mismo
# cruce. ``procedencia`` es el unico que los otros dos no traen.
CAMPOS = (
    'nombre', 'telefono', 'whatsapp', 'correo', 'web',
    'lat', 'lng', 'municipio', 'provincia', 'calle', 'sector',
    'categoria', 'descripcion', 'horario', 'estado', 'cerrado',
    'procedencia',
)


def abrir_texto(ruta, modo='rt'):
    """El archivo de fichas, comprimido o plano, segun su nombre.

    Solo modos de texto: quien escribe pasa ``'wt'`` y quien lee ``'rt'``.
    """
    if str(ruta).endswith('.gz'):
        return gzip.open(ruta, modo, encoding='utf-8')
    return open(ruta, modo, encoding='utf-8')


def datos_de(negocio):
    """La ficha entera como el diccionario plano que entienden los demas.

    Las franjas de horario salen como ``time`` de verdad (el mismo
    contrato que arma ``osm.parse_hours``); quien las serializa lo hace
    en ``a_linea``. Los dias marcados como cerrados **no viajan**: no son
    horario (``pendientes.faltantes_de`` no los cuenta), y el frontend
    los muestra igual — sin franja abierta, ese dia no esta.
    """
    loc = getattr(negocio, 'location', None)
    contact = getattr(negocio, 'contact', None)
    operativo = negocio.operational_status

    return {
        'nombre': negocio.name or '',
        'telefono': contact.phone if contact else '',
        'whatsapp': contact.whatsapp if contact else '',
        'correo': contact.email if contact else '',
        'web': contact.website if contact else '',
        'lat': float(loc.latitude) if loc and loc.latitude is not None else None,
        'lng': float(loc.longitude) if loc and loc.longitude is not None else None,
        'municipio': loc.municipality if loc else '',
        'provincia': loc.province if loc else '',
        'calle': loc.street if loc else '',
        'sector': loc.sector if loc else '',
        'categoria': (negocio.category.name if negocio.category else ''),
        'descripcion': negocio.description or '',
        'horario': [
            {'day': h.day,
             'open': h.open_time,
             'close': h.close_time}
            for h in negocio.hours.all()
            if h.open_time and h.close_time and not h.is_closed
        ],
        # El estado operativo se lleva como lo que es: su slug. Si la
        # ficha no lo tiene, va vacio y quien carga decide con lo poco que
        # haya — nunca rellenandolo por adivinar.
        'estado': operativo.slug if operativo else '',
        'cerrado': False,
        'procedencia': negocio.procedencia,
    }


def a_linea(datos):
    """``datos`` a una linea JSON con las horas en texto."""
    copia = {clave: datos.get(clave) for clave in CAMPOS}
    copia['horario'] = [
        {'day': f['day'],
         'open': f['open'].strftime('%H:%M'),
         'close': f['close'].strftime('%H:%M')}
        for f in datos.get('horario', [])
    ]
    return json.dumps(copia, ensure_ascii=False)


def desde_linea(linea):
    """Una linea JSON a ``datos``, con las horas otra vez como ``time``.

    Lo que no se pueda leer se ignora franja por franja en vez de
    tumbar la carga entera: un horario malo es peor que ningun horario,
    pero no justifica dejar el resto del archivo sin importar.
    """
    datos = json.loads(linea)
    franjas = []
    for f in datos.get('horario') or []:
        if not isinstance(f, dict):
            continue
        try:
            franjas.append({
                'day': f['day'],
                'open': dt_time.fromisoformat(str(f['open'])),
                'close': dt_time.fromisoformat(str(f['close'])),
            })
        except (KeyError, TypeError, ValueError):
            continue
    datos['horario'] = franjas
    return datos
