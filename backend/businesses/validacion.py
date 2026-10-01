"""Validacion de entrada: que se acepta y que se rechaza en la puerta.

Hay dos preguntas distintas y este modulo responde solo a la primera:

* **¿Se puede dejar entrar esto?** -> ``validar``. Un dato malformado no
  se queda en ninguna cola: se rechaza con su motivo (DISENO.md 11.5).
* **¿Que le falta ya estando dentro?** -> ``pendientes.py``. Eso no se
  rechaza, se acumula hasta que alguien lo complete.

Y una tercera, que es la que obliga §10-d: **¿este negocio ya existe?**
Cruzar ANTES de publicar no es opcional — OSM trae telefonos que en muchos
casos nosotros no tenemos, y publicar dos veces el mismo negocio es peor
que no publicarlo (§10-e).

Lo usan por igual el importador de OSM y el canal de envio de §11.5: si
cada uno validara a su manera, lo que entra por un lado y por el otro no
seria comparable.
"""
import re

from .geografia import (
    RADIO_KM,
    haversine_distance,
    normalizar,
)

# Un telefono valido: delimitado a caracteres de telefono y con digitos
# suficientes. No se valida el pais ni la operadora: lo que importa es si
# con eso se puede llamar (§10-f).
_TELEFONO = re.compile(r'\+?[\d\s().-]{6,30}')
MINIMO_DIGITOS = 7

# Cuantos caracteres minimos tiene que compartir un nombre para que
# "Panaderia Sol" y "Panaderia Sol (Moca)" puedan ser el mismo negocio.
MINIMO_CLAVE_DUPLICADO = 4

# Si los puntos estan a menos de esto y los nombres se contienen mutuamente,
# es el mismo negocio en la misma esquina.
MARGEN_DUPLICADO_KM = 0.1


def limpiar_telefono(valor):
    """El primer telefono de la cadena, sin el prefijo ``tel:`` de OSM.

    En OSM aparecen cosas como ``tel:+18095551234`` o varios numeros
    separados por ``;``. El primero basta: lo que importa es si hay con
    que llamar.
    """
    texto = (valor or '').strip()
    if not texto:
        return ''
    texto = re.sub(r'^tel:', '', texto, flags=re.IGNORECASE).strip()
    return re.split(r'[;,/|]', texto)[0].strip()


def telefono_valido(valor):
    """¿Se puede llamar a esto? Vacio no es valido (aunque si permitido)."""
    texto = (valor or '').strip()
    if not texto or not _TELEFONO.fullmatch(texto):
        return False
    return sum(c.isdigit() for c in texto) >= MINIMO_DIGITOS


def validar(*, nombre, telefono, lat, lng, municipio, cabecera,
            radio_km=RADIO_KM):
    """Los motivos por los que un dato NO se deja entrar. [] = pasa.

    **No evalua el trio.** Que falte el telefono o el punto no rechaza:
    eso es un pendiente y se acumula (§10-g). Aqui solo se descarta lo que
    esta mal formado o que no se puede verificar.

    ``cabecera`` es obligatoria: sin ella no hay forma de comprobar que
    las coordenadas caen en el municipio que dice ser (§11.5). En la
    practica siempre existe — el municipio sale del padron de la seccion 9.

    ``radio_km`` es el circulo con que se comprueba: 5 por defecto, que es
    el de R1. El importador lo puede ampliar con ``--radio``; el canal de
    envio no, porque lo que entra por ahi tiene que poder verse a 5 km.
    """
    motivos = []

    clave = normalizar(nombre)
    if not clave:
        motivos.append('Sin nombre.')
    elif len(clave) < 2:
        motivos.append('El nombre es demasiado corto para identificarlo.')

    if not (municipio or '').strip():
        motivos.append('Sin municipio.')
    elif cabecera is None:
        motivos.append('Municipio fuera del padron de cabeceras.')

    if telefono and not telefono_valido(telefono):
        motivos.append('El telefono no tiene un formato valido.')

    # Sin coordenadas NO se rechaza: falta el punto, y eso es trio
    # incompleto (§10-g -> reporte), no un dato mal formado. Lo que si se
    # rechaza es que vengan a medias, que no es ni una cosa ni la otra.
    # El circulo solo se puede comprobar cuando hay punto.
    if (lat is None) != (lng is None):
        motivos.append('Coordenadas incompletas: falta latitud o longitud.')
    elif lat is not None and cabecera is not None:
        distancia = haversine_distance(lat, lng, cabecera['lat'], cabecera['lng'])
        if distancia > radio_km:
            motivos.append(
                'Las coordenadas caen a %.1f km de la cabecera de %s: '
                'fuera del circulo de %g km.'
                % (distancia, cabecera['municipio'], radio_km)
            )

    return motivos


def indice_de_nombres(negocios):
    """Cruce en lote: ``{nombre normalizado: negocio}``.

    Se construye una vez por municipio y se consulta por candidato. Meter
    una consulta por candidato seria O(n*m) contra la base.
    """
    indice = {}
    for biz in negocios:
        clave = normalizar(biz.name)
        if clave:
            indice.setdefault(clave, biz)
    return indice


def duplicado(indice, nombre, lat=None, lng=None):
    """El negocio existente que ya describe ese nombre, o ``None``.

    Dos comprobaciones, en este orden:

    1. el mismo nombre normalizado en el mismo municipio;
    2. un nombre que contiene al otro (o al revues) con al menos
       ``MINIMO_CLAVE_DUPLICADO`` caracteres y a menos de
       ``MARGEN_DUPLICADO_KM``: "Panaderia Sol" y "Panaderia Sol (Moca)"
       en la misma esquina son el mismo negocio.

    La segunda recorre el indice entero, por eso solo se llega a ella si
    la primera no ha servido.
    """
    clave = normalizar(nombre)
    if not clave:
        return None

    coincidencia = indice.get(clave)
    if coincidencia:
        return coincidencia

    if lat is None or lng is None:
        return None

    for otra_clave, otro in indice.items():
        if min(len(clave), len(otra_clave)) < MINIMO_CLAVE_DUPLICADO:
            continue
        if clave not in otra_clave and otra_clave not in clave:
            continue
        loc = getattr(otro, 'location', None)
        if loc is None or loc.lat is None or loc.lng is None:
            continue
        if haversine_distance(lat, lng, loc.lat, loc.lng) <= MARGEN_DUPLICADO_KM:
            return otro
    return None
