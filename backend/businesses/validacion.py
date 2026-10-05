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


def enriquecer(negocio, datos, *, categoria=None):
    """Rellena en la ficha existente lo que le falta. **Nunca sobrescribe.**

    Es la otra mitad de §10-d: si la fuente trae el telefono y nosotros no
    lo tenemos, se le pone a la ficha que ya existe en vez de publicar una
    segunda por ese motivo. Al reves tambien: si nosotros ya lo teniamos,
    se queda lo nuestro.

    Cubre **todos** los campos del reporte de §11.1, no solo el contacto:
    si el formulario de la Fase D no pudiera completar nombre, punto,
    categoria, descripcion o estado, el colaborador terminaria de llenar
    un ficha y el reporte se quedaria marcandola igual, es decir no
    acabaria nunca.

    Devuelve la lista de lo que se toco (vacía = no hizo falta nada).

    ``datos`` es el mismo diccionario que produce ``osm.a_datos`` y que
    arma el endpoint de levantamiento, para que los dos crucen igual.
    ``categoria`` es opcional y viene **ya resuelta** por quien llama: el
    importador la crea si no existe y el canal solo busca la que ya hay,
    para que una errata no le abra una categoria nueva al sistema.
    """
    from business_contacts.models import BusinessContact

    tocado = []

    contact = getattr(negocio, 'contact', None)
    if contact is None:
        if any((datos.get('telefono'), datos.get('whatsapp'),
                datos.get('correo'), datos.get('web'))):
            BusinessContact.objects.create(
                business=negocio,
                phone=datos.get('telefono', ''),
                whatsapp=datos.get('whatsapp', ''),
                email=datos.get('correo', ''),
                website=datos.get('web', ''),
            )
            tocado.append('contacto')
    else:
        for campo, valor in (
            ('phone', datos.get('telefono')),
            ('whatsapp', datos.get('whatsapp')),
            ('email', datos.get('correo')),
            ('website', datos.get('web')),
        ):
            if valor and not (getattr(contact, campo) or '').strip():
                setattr(contact, campo, valor)
                tocado.append(campo)
        if tocado:
            contact.save()

    loc = getattr(negocio, 'location', None)
    if loc is not None:
        cambios = []
        if not (loc.street or '').strip() and datos.get('calle'):
            loc.street = datos['calle']
            cambios.append('street')
        if not (loc.sector or '').strip() and datos.get('sector'):
            loc.sector = datos['sector']
            cambios.append('sector')
        if not (loc.referencias or '').strip() and datos.get('referencias'):
            loc.referencias = datos['referencias']
            cambios.append('referencias')
        # El punto: los DOS juntos o ninguno. Un ficha a medias seria
        # peor que una sin punto, porque pasaria la puerta del circulo
        # sin tener sitio de verdad.
        if (loc.latitude is None or loc.longitude is None) \
                and datos.get('lat') is not None \
                and datos.get('lng') is not None:
            loc.latitude = datos['lat']
            loc.longitude = datos['lng']
            cambios.append('punto')
        if cambios:
            campos = [c for c in cambios if c != 'punto']
            if 'punto' in cambios:
                campos.extend(['latitude', 'longitude'])
            loc.save(update_fields=campos)
            tocado.extend(cambios)

    if datos.get('horario') and not negocio.hours.exists():
        from .ingreso import poner_horario
        poner_horario(negocio, datos['horario'])
        tocado.append('horario')

    # Lo que va en el propio negocio y todavia no tiene. Se guarda en una
    # sola llamada porque son campos de la misma fila. Van DOS listas:
    # `cambios` en el vocabulario del reporte (es lo que se devuelve como
    # "completado") y `campos`, que es como se llaman de verdad en el
    # modelo — `update_fields` no perdona un nombre inventado.
    cambios = []
    campos = []
    if not (negocio.name or '').strip() and datos.get('nombre'):
        negocio.name = datos['nombre']
        cambios.append('nombre')
        campos.append('name')
    if not (negocio.description or '').strip() and datos.get('descripcion'):
        negocio.description = datos['descripcion']
        cambios.append('descripcion')
        campos.append('description')
    if negocio.category_id is None and datos.get('categoria'):
        if categoria is None:
            from categories.models import Category
            categoria = Category.objects.filter(
                name__iexact=datos['categoria'],
            ).first()
        if categoria is not None:
            negocio.category = categoria
            cambios.append('categoria')
            campos.append('category')
    if negocio.operational_status_id is None and datos.get('estado'):
        from operational_status.models import OperationalStatus
        operativo = OperationalStatus.objects.filter(
            slug=datos['estado'],
        ).first()
        if operativo is not None:
            negocio.operational_status = operativo
            cambios.append('estado')
            campos.append('operational_status')
    if cambios:
        # El slug se guarda solo si acaba de ponerse el nombre: sin el,
        # un ficha que entro sin nombre se quedaria sin URL por mucho que
        # ahora le llamemos Panaderia El Trigal.
        if 'nombre' in cambios:
            campos.append('slug')
        negocio.save(update_fields=campos)
        tocado.extend(cambios)

    return tocado
