"""POST /api/levantamiento/ — el canal de envio del levantamiento (§11.5).

**No hay acceso, hay envio.** El colaborador no entra a nada ni lee nada:
solo firma con su token. Eso es lo que deja montar el canal completo sin
montar autenticacion —y bloquear a UNO sin cerrar a los demas—.

Tres reglas, en este orden, y cada una es una decision distinta:

1. **Validar en la puerta.** Lo mal formado se rechaza con sus motivos y
   no queda pendiente de nada (§11.5). Lo que solo le falta el trio NO se
   rechaza — eso seria esconderlo (§10-g).
2. **Cruzar.** Si el negocio ya existe no se crea una segunda ficha: se le
   completa lo que le falta a la que ya esta (§10-d).
3. **Publicar solo el trio.** nombre + telefono + punto -> publicado; sin
   eso -> pendiente, y sale en el reporte de su municipio (§10-f/g).

Quien decide es el sistema en los tres: quien envia no publica (§11-j).

El token solo se acepta en cabecera (``X-Colaborador-Token`` o
``Authorization: Bearer``). Por la URL se quedaria en los registros del
servidor y en el historial del navegador, que es justo donde no queremos
que se filtre algo que firma envios enteros.
"""
from datetime import time as dt_time, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.response import Response

from categories.models import Category
from publication_status.models import PublicationStatus

from . import geografia, ingreso, pendientes, validacion
from .firma import colaborador_de
from .models import Business, Envio

# Un techo, no una politica: de verdad quien esta en la calle manda de a
# pocos por minuto. Basta para cortar un bombardeo y no estorba a nadie.
LIMITE_ENVIOS_POR_MINUTO = 30

# Copia exacta de la cabecera, para que quien la recibe pueda compartirla
# sin tener que adivinar si esta en minusculas o con coma.
AUTENTICACION_DE_ESCRITURA = []


def _ip(request):
    """La primera IP de ``X-Forwarded-For`` (que es lo que pone Render).

    Solo para mirar si un lote de envios viene de un solo sitio. Nada se
    decide por aqui: el bloqueo es por token, no por IP, que detras de un
    operador movil comparten varias personas.
    """
    for clave in ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'):
        crudo = request.META.get(clave, '')
        if not crudo:
            continue
        candidato = crudo.split(',')[0].strip()
        try:
            validate_ipv46_address(candidato)
        except ValidationError:
            continue
        return candidato
    return None


def _horario(bruto):
    """``[{"dia": "Lunes", "desde": "08:00", "hasta": "17:00"}]`` a franjas.

    Lo que no se entienda se ignora, **nunca se inventa**: un horario malo
    es peor que ningun horario, y ademas el campo sigue apareciendo como
    pendiente si queda a medias.
    """
    from business_hours.models import BusinessHours

    if not isinstance(bruto, list):
        return []

    validos = {
        nombre.lower(): valor
        for valor, nombre in BusinessHours.DayOfWeek.choices
    }
    franjas = []
    for item in bruto[:14]:
        if not isinstance(item, dict):
            continue
        dia = validos.get(str(item.get('dia', '')).strip().lower())
        try:
            desde = dt_time.fromisoformat(str(item.get('desde', ''))[:5])
            hasta = dt_time.fromisoformat(str(item.get('hasta', ''))[:5])
        except ValueError:
            continue
        if dia and desde < hasta:
            franjas.append({'day': dia, 'open': desde, 'close': hasta})
    return franjas


def _a_datos(cuerpo):
    """El cuerpo JSON al diccionario que entienden ``validar`` e ``ingreso``.

    Es el **mismo** que arma ``osm.a_datos``: si los dos produjeran formas
    distintas, el importador y el canal entrarian fichas con pinta
    diferente y el reporte de §11.1 contaria una cosa u otra segun de
    donde vinieran.

    Devuelve ``(datos, motivos)``: aqui solo se recoge lo mal formado del
    cuerpo en si; lo que se comprueba contra el municipio lo hace
    ``validar`` a continuacion, para no mezclar los dos criterios.
    """
    motivos = []

    def texto(clave, tope):
        valor = cuerpo.get(clave)
        if valor is None:
            return ''
        if not isinstance(valor, str):
            motivos.append('"%s" tiene que ser texto.' % clave)
            return ''
        return valor.strip()[:tope]

    def coordenada(clave):
        valor = cuerpo.get(clave)
        if valor is None or valor == '':
            return None
        try:
            return float(valor)
        except (TypeError, ValueError):
            # Diferente de "no vino": vino, pero no es un numero. Si se
            # convirtiera a ``None`` esto pasaria por "falta el punto"
            # (que se perdona) en vez de "esta roto" (que se rechaza).
            motivos.append('"%s" tiene que ser un numero.' % clave)
            return None

    datos = {
        'nombre': texto('nombre', 200),
        'telefono': texto('telefono', 30),
        'whatsapp': texto('whatsapp', 30),
        'correo': texto('correo', 100),
        'web': texto('web', 200),
        'lat': coordenada('lat'),
        'lng': coordenada('lng'),
        'municipio': texto('municipio', 100),
        'provincia': '',
        'calle': texto('calle', 200),
        'sector': texto('sector', 100),
        'categoria': texto('categoria', 100),
        'descripcion': texto('descripcion', 300),
        'horario': _horario(cuerpo.get('horario')),
        'cerrado': bool(cuerpo.get('cerrado')),
    }
    return datos, motivos


def _para_json(datos):
    """Copia serializable de ``datos`` para guardarla en ``Envio.datos``.

    Sin esto el ``time`` de las franjas revienta el JSONField — y hay que
    guardarlo: es la prueba de lo que llego.
    """
    copia = dict(datos)
    copia['horario'] = [
        {'dia': f['day'],
         'desde': f['open'].isoformat(),
         'hasta': f['close'].isoformat()}
        for f in datos.get('horario', [])
    ]
    return copia


def _registrar(colaborador, estado, datos, motivos, faltan, negocio, request):
    """Un renglon de auditoria: quien firmo, que mando y que decidio.

    Sin esto el canal seria una caja negra, y §11.5 exige poder juzgar a
    UN colaborador concreto (lo cual es lo mismo que poder bloquear su
    token sin cerrar a los demas).
    """
    envio = Envio.objects.create(
        colaborador=colaborador,
        negocio=negocio,
        estado=estado,
        motivos=motivos,
        faltan=faltan,
        datos=_para_json(datos),
        ip=_ip(request),
    )
    colaborador.ultimo_envio = envio.recibido_el
    colaborador.save(update_fields=['ultimo_envio'])
    return envio


@api_view(['POST'])
# Sin autenticadores: DRF usaria SessionAuthentication, que le exige token
# CSRF a quien tenga la sesion del admin abierta — y el admin y esta
# herramienta estan en el MISMO dominio, asi que le pasaria a cualquiera
# que probara. Nada aqui se hace pasar por nadie: la puerta es el token.
@authentication_classes(AUTENTICACION_DE_ESCRITURA)
@permission_classes([permissions.AllowAny])
def levantamiento(request):
    """Un envio del canal: validar -> cruzar -> publicar si hay trio."""
    colaborador = colaborador_de(request)
    if colaborador is None:
        return Response(
            {'detail': 'Firma de colaborador invalida o inactiva.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    hace_un_minuto = timezone.now() - timedelta(minutes=1)
    envios = Envio.objects.filter(
        colaborador=colaborador, recibido_el__gte=hace_un_minuto,
    ).count()
    if envios >= LIMITE_ENVIOS_POR_MINUTO:
        return Response(
            {'detail': 'Demasiados envios en el ultimo minuto.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    cuerpo = request.data if isinstance(request.data, dict) else {}
    datos, motivos = _a_datos(cuerpo)

    cabecera = None
    if not motivos:
        cabecera = geografia.cabecera_para(datos['municipio'])
        if cabecera is not None:
            datos['provincia'] = cabecera['provincia']
        # Aqui entra R1 sin ampliaciones: el radio es el de geografia
        # (5 km), y el canal no lo puede ensanchar (§10-j).
        motivos = validacion.validar(
            nombre=datos['nombre'],
            telefono=datos['telefono'],
            lat=datos['lat'],
            lng=datos['lng'],
            municipio=datos['municipio'],
            cabecera=cabecera,
        )

    # --------------------- 1. la puerta ------------------------------
    if motivos:
        envio = _registrar(
            colaborador, 'rechazado', datos, motivos, [], None, request,
        )
        return Response(
            {'estado': 'rechazado', 'motivos': motivos, 'faltan': [],
             'recibo': envio.id},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------- 2. el cruce -------------------------------
    # Solo el municipio declarado y el canónico: mas que eso seria
    # escanear la base entera en cada envio. Lo acentos distintos entre
    # un nombre y otro quedan cubiertos por el segundo criterio de
    # `duplicado` (mismo sitio, <300 m), que es el que no depende de
    # como esté escrito el municipio.
    indice = validacion.indice_de_nombres(
        Business.objects.filter(
            Q(location__municipality__iexact=datos['municipio'])
            | Q(location__municipality__iexact=cabecera['municipio'])
        ).select_related('location')
    )
    existente = validacion.duplicado(
        indice, datos['nombre'], datos['lat'], datos['lng'],
    )

    if existente is not None:
        completado = validacion.enriquecer(existente, datos)
        # Releer: `enriquecer` dejo en la instancia la cache de "no tiene
        # contacto" de antes de crearlo, y con ella `cumple_trio` veria
        # el telefono que acaba de ponerse. Sin releer, la ficha se quedaria
        # en revision a pesar de que ya cumple el trio.
        existente = Business.objects.get(pk=existente.pk)
        if completado:
            # `publicar_si_cumple` actualiza la instancia y la guarda.
            pendientes.publicar_si_cumple(
                [existente], PublicationStatus.objects.get(slug='publicado'),
            )
        faltan = pendientes.faltantes_de(existente)
        envio = _registrar(
            colaborador, 'duplicado', datos, [], faltan, existente, request,
        )
        return Response({
            'estado': 'duplicado',
            'motivos': [],
            'faltan': faltan,
            'completado': completado,
            'recibo': envio.id,
        })

    # ------------------- 3. entrar y publicar ------------------------
    categoria = None
    if datos['categoria']:
        # Solo se BUSCA: aqui teclea una persona y una errata no debe
        # abrirle una categoria nueva al sistema. (El importador si la
        # crea, porque el nombre viene de OSM y es de fiar.)
        categoria = Category.objects.filter(
            name__iexact=datos['categoria'],
        ).first()

    negocio = ingreso.crear(
        datos,
        categoria=categoria,
        en_revision=PublicationStatus.objects.get(slug='en-revision'),
        procedencia='levantado',
    )
    publicadas = pendientes.publicar_si_cumple(
        [negocio], PublicationStatus.objects.get(slug='publicado'),
    )
    faltan = pendientes.faltantes_de(negocio)
    estado = 'publicado' if publicadas else 'pendiente'

    envio = _registrar(
        colaborador, estado, datos, [], faltan, negocio, request,
    )
    return Response(
        {'estado': estado, 'motivos': [], 'faltan': faltan,
         'recibo': envio.id},
        status=status.HTTP_201_CREATED,
    )
