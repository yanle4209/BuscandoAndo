"""Entrada de datos: montar la ficha completa a partir de datos planos.

El mismo camino para el importador de OSM y para el canal de envio de
§11.5. Si cada uno montara su ``Business`` a su manera, los dos entrarian
con formas distintas y el reporte de §11.1 contaria una cosa u otra segun
de donde vinieran — que es justo lo que §10-i queria evitar al reunir el
trio en un solo sitio.
"""
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from business_locations.models import BusinessLocation
from operational_status.models import OperationalStatus

from .models import Business


def crear(datos, *, categoria, en_revision, procedencia='importado'):
    """La ficha entera —negocio, ubicacion, contacto y horario—.

    ``datos`` es el diccionario que comparten ``osm.a_datos`` y el
    endpoint de levantamiento. El nombre de categoria ya viene resuelto
    por quien llama: el importador la crea si no existe, mientras que el
    canal de envio solo busca la que ya hay, para que una errata no le
    abra una categoria nueva al sistema.

    Siempre entra como ``en-revision``: quien la publica es
    ``pendientes.publicar_si_cumple``, y solo si cumple el trio.

    El estado operativo se busca con ``filter().first()`` y no con
    ``get()``: es nullable y opcional, y un sembrado a medias no puede
    tumbar el envio de alguien que esta en la calle. El de publicacion si
    que hace falta de verdad —sin el no hay en que poner la ficha—, por
    eso ese viene de fuera.
    """
    # El estado declarado manda; si no viene ninguno (cliente viejo, o
    # "sin decidir" en el formulario) se cae en el criterio de siempre,
    # que es el de la casilla "esta cerrado". Se busca con
    # `filter().first()` y no con `get()`: es nullable y opcional, y un
    # sembrado a medias no puede tumbar el envio de alguien que esta en
    # la calle.
    operativo = (
        OperationalStatus.objects.filter(slug=datos['estado']).first()
        if datos.get('estado')
        else (
            OperationalStatus.objects.filter(slug='cerrado').first()
            if datos.get('cerrado')
            else OperationalStatus.objects.filter(slug='abierto').first()
        )
    )
    negocio = Business.objects.create(
        name=datos['nombre'],
        # Sin inventar: lo que no venga queda vacio y por eso aparece
        # como pendiente en el reporte (§10: "nada se rellena por
        # inventar").
        description=datos.get('descripcion') or '',
        short_description='',
        category=categoria,
        publication_status=en_revision,
        operational_status=operativo,
        procedencia=procedencia,
    )
    BusinessLocation.objects.create(
        business=negocio,
        street=datos.get('calle') or '',
        sector=datos.get('sector') or '',
        municipality=datos['municipio'],
        province=datos.get('provincia') or '',
        latitude=datos['lat'],
        longitude=datos['lng'],
    )
    if any((datos.get('telefono'), datos.get('whatsapp'),
            datos.get('correo'), datos.get('web'))):
        BusinessContact.objects.create(
            business=negocio,
            phone=datos.get('telefono') or '',
            whatsapp=datos.get('whatsapp') or '',
            email=datos.get('correo') or '',
            website=datos.get('web') or '',
        )
    poner_horario(negocio, datos.get('horario') or [])
    return negocio


def poner_horario(negocio, franjas):
    """Las franjas del diccionario de ``datos`` a ``BusinessHours``."""
    for franja in franjas:
        BusinessHours.objects.get_or_create(
            business=negocio,
            day=franja['day'],
            defaults={
                'open_time': franja['open'],
                'close_time': franja['close'],
            },
        )
