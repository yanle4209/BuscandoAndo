"""POST /api/levantamiento/ — el canal de envio del levantamiento (§11.5).

**No hay acceso, hay envio.** El colaborador no entra a nada ni lee nada:
solo firma con su token. Eso es lo que deja montar el canal completo sin
montar autenticacion —y bloquear a UNO sin cerrar a los demas—.

Tres reglas, en este orden, y cada una es una decision distinta:

1. **Validar en la puerta.** Lo mal formado se rechaza con sus motivos y
   no queda pendiente de nada (§11.5). Lo que solo le falta un
   obligatorio NO se rechaza — eso seria esconderlo (§10-g).
2. **Cruzar.** Si el negocio ya existe no se crea una segunda ficha: se le
   completa lo que le falta a la que ya esta (§10-d).
3. **Publicar solo con los obligatorios.** nombre + direccion + telefono +
   imagen + punto -> publicado; sin eso -> pendiente, y sale en el
   reporte de su municipio (§10-f/g).

Quien decide es el sistema en los tres: quien envia no publica (§11-j).

El cuerpo puede traer ademas ``ficha`` (el id de una ficha ya existente),
que enciende el **modo completar** de la Fase D: el formulario sale
poblado con lo que ya hay y lo que se manda se escribe EN ESA ficha. Sin
el id el cruce de la regla 2 seria a ciegas y podria enriquecer el
negocio de al lado; con el id hace falta ademas que la ficha este en el
municipio del token (§11-i, la misma llave con la que se LEE el reporte).

Dos cosas mas que nacen con el formulario del levantamiento:

* **La foto es obligatoria** hasta que la ficha tenga al menos una.
  Entra por ``imagenes`` (multipart), se abre con Pillow igual que en
  el admin, se guarda recortada a 1200x675 en WebP por
  ``BusinessImage.save()`` y hay techo de 5 por ficha. Es ademas uno de
  los **obligatorios**: sin foto no se publica, y por eso las fichas sin
  foto salen en el reporte de revision aunque ya esten publicadas.

* **La categoria se puede crear** desde el formulario, con la bandera
  ``categoria_nueva``: el servidor la valida al momento (nombre, sin
  duplicar, slug unico —si ya hay una con ese slug, esa es—) y la da
  de alta en el envio. La respuesta lo confirma, para que nadie se
  quede con la duda de si paso: ``categoria_creada`` con el nombre si
  nacio aqui, ``categoria_reusada`` si ya estaba y no se duplica otra.
  Sin la bandera sigue valiendo lo de siempre: solo se busca, porque
  una errata no debe abrirle una categoria nueva al sistema.

El token solo se acepta en cabecera (``X-Colaborador-Token`` o
``Authorization: Bearer``). Por la URL se quedaria en los registros del
servidor y en el historial del navegador, que es justo donde no queremos
que se filtre algo que firma envios enteros.
"""
import json
from datetime import time as dt_time, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image
from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.response import Response

from business_images.models import MAX_IMAGES_PER_BUSINESS, BusinessImage
from categories.models import Category
from publication_status.models import PublicationStatus

from . import geografia, ingreso, pendientes, validacion
from .firma import colaborador_de
from .models import Business, Envio

# Un techo, no una politica: de verdad quien esta en la calle manda de a
# pocos por minuto. Basta para cortar un bombardeo y no estorba a nadie.
LIMITE_ENVIOS_POR_MINUTO = 30

# Los estados operativos que el formulario puede declarar. Lista, no
# consulta: se comprueba en la puerta, y resolverla es un `filter()`
# mas que no hace falta pagar en cada envio.
ESTADOS_VALIDOS = ('abierto', 'cerrado', 'por-horario', 'cerrado-permanente')

# Copia exacta de la cabecera, para que quien la recibe pueda compartirla
# sin tener que adivinar si esta en minusculas o con coma.
AUTENTICACION_DE_ESCRITURA = []


def _en_su_municipio(colaborador, ficha):
    """§11-i: el token solo ESCRIBE en su municipio, igual que solo lo lee.

    Se compara normalizado por lo mismo que en el reporte: el nombre de
    ``Colaborador.municipio`` lo teclea el admin y el de la ficha viene
    de texto libre. Un ficha sin ubicacion no tiene municipio que
    comprobar, y por eso no entra — que ademas es justo como la agrupa el
    reporte, que la manda a «(sin municipio)».
    """
    asignado = (colaborador.municipio or '').strip()
    if not asignado:
        return False
    loc = getattr(ficha, 'location', None)
    municipio = (getattr(loc, 'municipality', '') or '') if loc else ''
    if not municipio:
        return False
    return geografia.normalizar(asignado) == geografia.normalizar(municipio)


def _ip(request):
    """La IP del cliente real (para mirar, no para decidir).

    Detras de Cloudflare/Render la cadena ``X-Forwarded-For`` no se lee
    a ojo: el cliente puede anteponer lo que quiera y cada proxy anade
    el suyo al final, donde acaba la direccion del borde de
    Cloudflare, que es la misma para todos. Cloudflare mantiene ademas
    ``CF-Connecting-IP`` con el visitante de verdad, y esa solo la puede
    escribir el: si llega, manda ella. Si no llega, se toma la ultima
    entrada valida de la cadena (la que declaro el ultimo proxy, que el
    cliente no puede reescribir), y si no hay cadena, ``REMOTE_ADDR``.

    Solo para mirar si un lote de envios viene de un solo sitio. Nada se
    decide por aqui: el bloqueo es por token, no por IP, que detras de un
    operador movil comparten varias personas.
    """
    conector = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
    if conector:
        try:
            validate_ipv46_address(conector)
            return conector
        except ValidationError:
            pass
    crudo = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidatos = [p.strip() for p in crudo.split(',') if p.strip()]
    if not candidatos:
        candidatos = [request.META.get('REMOTE_ADDR', '')]
    for candidato in reversed(candidatos):
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

    if isinstance(bruto, str):
        # El formulario manda multipart: ahi el JSON del horario viaja
        # como texto. Lo que no sea JSON valido se ignora, igual que
        # cualquier otra franja mal formada.
        try:
            bruto = json.loads(bruto)
        except ValueError:
            return []

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


def _booleano(valor):
    """Una casilla del cuerpo, venga como venga: ``true`` del JSON o
    'true'/'1'/'on'/'yes' del multipart.

    Sin esto ``bool('false')`` daria True y TODO lo que llegara por el
    formulario saldria cerrado — en multipart todos los valores son
    texto. Lo demas (ausente, ``None``, cualquier cadena rara) apagado.
    """
    if isinstance(valor, str):
        return valor.strip().lower() in ('true', '1', 'on', 'yes')
    return bool(valor)


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

    estado = texto('estado', 40)
    if estado and estado not in ESTADOS_VALIDOS:
        # Mal formado: no es un pendiente de rellenar despues, es un
        # cuerpo que no dice nada que se pueda guardar (§11.5).
        motivos.append('"estado" no es un estado valido.')

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
        'referencias': texto('referencias', 300),
        'categoria': texto('categoria', 100),
        'descripcion': texto('descripcion', 300),
        'horario': _horario(cuerpo.get('horario')),
        'cerrado': _booleano(cuerpo.get('cerrado')),
        'estado': estado,
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


def _abrible(archivo):
    """Pillow abre y carga el archivo: lo que exige un ImageField.

    Al final se rebobina pase lo que pase: si no, el puntero queda al
    final y ``BusinessImage.save()``, que vuelve a abrirlo, subiria un
    fichero vacio.
    """
    try:
        with Image.open(archivo) as imagen:
            imagen.load()
    except Exception:
        abrible = False
    else:
        abrible = True
    try:
        archivo.seek(0)
    except Exception:                                    # pragma: no cover
        pass
    return abrible


def _validar_imagenes(archivos, existentes):
    """La puerta de las fotos: abribles y hasta 5 en total.

    Mismas reglas que el formulario del admin: Django abre la imagen
    con Pillow antes de dejarla pasar, y el modelo corta en
    ``MAX_IMAGES_PER_BUSINESS``. Aqui solo se MIRA —el guardado, el
    recorte y el WebP, lo hace ``BusinessImage.save()``—; quien manda
    las fotos no las procesa nunca en el cliente.
    """
    motivos = []
    for archivo in archivos:
        if not _abrible(archivo):
            motivos.append('"imagenes" tiene que ser una imagen.')
            break
    if not motivos and existentes + len(archivos) > MAX_IMAGES_PER_BUSINESS:
        motivos.append('Se aceptan hasta 5 imagenes por ficha.')
    return motivos


def _guardar_imagenes(negocio, archivos):
    """Cada foto entra por ``BusinessImage``: ahi se recorta y va a WebP.

    El orden continua desde las que ya hay, para que el listado —que
    ordena por ``order``— enseñe las fotos en el en que llegaron.
    """
    base = BusinessImage.objects.filter(business=negocio).count()
    for posicion, archivo in enumerate(archivos, start=base):
        BusinessImage.objects.create(
            business=negocio, image=archivo, order=posicion,
        )


def _categoria_nueva(nombre):
    """Alta inmediata de la categoria que el formulario pide crear.

    Devuelve ``(categoria, error, creada)``: ``creada`` dice si nacio
    aqui —lo que la respuesta lleva al formulario para confirmarlo—.
    Misma regla que en el importador: si ya hay una con ese nombre
    —sin distinguir mayusculas— o con ese slug, esa es y no se crea
    otra; dos con el mismo slug reventarian el unique de la tabla. El
    ``IntegrityError`` es la carrera entre la consulta y el insert:
    gana la que acabo de nacer.
    """
    slug = slugify(nombre, allow_unicode=True)
    if not slug:
        return None, '"categoria" no sirve para crear una categoria.', False
    categoria = (
        Category.objects.filter(name__iexact=nombre).first()
        or Category.objects.filter(slug=slug).first()
    )
    if categoria is not None:
        return categoria, None, False
    try:
        return Category.objects.create(name=nombre, slug=slug), None, True
    except IntegrityError:
        # Otro proceso la creo entre la consulta y el insert: la que
        # acaba de nacer manda.
        return Category.objects.get(slug=slug), None, False


def _registrar(colaborador, estado, datos, motivos, faltan, negocio, request):
    """Un renglon de auditoria: quien firmo, que mando y que decidio.

    Sin esto el canal seria una caja negra, y §11.5 exige poder juzgar a
    UN colaborador concreto (lo cual es lo mismo que poder bloquear su
    token sin cerrar a los demas).
    """
    envio = Envio.objects.create(
        colaborador=colaborador,
        firmante_nombre=colaborador.nombre,
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
    """Un envio del canal: validar -> cruzar -> publicar si cumple."""
    colaborador = colaborador_de(request)
    if colaborador is None:
        return Response(
            {'detail': 'Firma de colaborador invalida, inactiva o vencida.'},
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

    # ¿Completar la ficha que el colaborador ELIGIO en su reporte, o una
    # alta nueva? La diferencia importa: sin el id el cruce de la regla 2
    # se haria a ciegas, y podria enriquecer el negocio de al lado.
    ficha = None
    bruto = cuerpo.get('ficha')
    if bruto not in (None, ''):
        try:
            pk_ficha = int(bruto)
        except (TypeError, ValueError):
            motivos.append('"ficha" tiene que ser un numero.')
        else:
            ficha = (
                Business.objects
                .select_related('location', 'contact')
                .filter(pk=pk_ficha)
                .first()
            )
            if ficha is None:
                motivos.append('Esa ficha no existe.')
            elif not _en_su_municipio(colaborador, ficha):
                # 403 y no "rechazado": no es que los datos esten mal,
                # es que a este token no le toca. Se parece a lo que hace
                # el reporte al pedir el municipio de otro.
                return Response(
                    {'detail': 'A este token le toca otro municipio.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                datos['ficha'] = ficha.pk

    cabecera = None
    if not motivos:
        cabecera = geografia.cabecera_para(datos['municipio'])
        if cabecera is not None:
            datos['provincia'] = cabecera['provincia']
        # Sin circulo. El municipio lo garantiza el token (§11-i), no
        # una medicion desde la cabecera: un negocio a 9 km del centro
        # sigue siendo de ahi, y el circulo de 5 km es el del BUSCADOR
        # (R1), no el de quien levanta la ficha. El importador, que viene
        # de OSM y no de un token, sigue midiendo.
        motivos = validacion.validar(
            nombre=datos['nombre'],
            telefono=datos['telefono'],
            lat=datos['lat'],
            lng=datos['lng'],
            municipio=datos['municipio'],
            cabecera=cabecera,
            radio_km=None,
        )

    # Las fotos: mismas reglas que el formulario del admin —Pillow
    # abre el archivo y el modelo corta en 5—. Van DESPUES de resolver
    # la ficha, porque "¿tiene ya foto?" solo se sabe con la ficha a la
    # mano, y es lo que decide si una foto es obligatoria. Van ANTES
    # que la categoria: esta solo nace si el envio entero se va a
    # aceptar, para no dejar una hoja suelta en la tabla por un envio
    # que termino rechazado.
    archivos = list(request.FILES.getlist('imagenes'))
    if archivos:
        datos['imagenes'] = [archivo.name for archivo in archivos]
    if not motivos:
        existentes = ficha.images.count() if ficha is not None else 0
        motivos += _validar_imagenes(archivos, existentes)
        if not motivos and not archivos and existentes == 0:
            if ficha is None:
                motivos.append('Una ficha nueva necesita al menos una foto.')
            else:
                motivos.append(
                    'Esta ficha no tiene ninguna foto: '
                    'hay que mandar al menos una.'
                )

    # Se resuelve una sola vez porque la usan los DOS caminos (completar
    # y alta). Sin la bandera solo se BUSCA: aqui teclea una persona y
    # una errata no debe abrirle una categoria nueva al sistema. Con
    # `categoria_nueva` el formulario dijo que no encontro la suya y
    # pide crearla — ahi si, validada al momento en `_categoria_nueva`.
    # El importador la crea siempre, porque el nombre viene de OSM.
    # El desenlace viaja en la respuesta (`categoria_creada` /
    # `categoria_reusada`): sin eso el formulario no tiene nada con que
    # confirmarle a la persona si su categoria salio o no.
    categoria = None
    categoria_creada = None
    categoria_reusada = None
    if not motivos and _booleano(cuerpo.get('categoria_nueva')):
        if not datos['categoria']:
            motivos.append(
                '"categoria" tiene que tener nombre para crear una '
                'categoria.'
            )
        else:
            categoria, error, creada = _categoria_nueva(datos['categoria'])
            if error:
                motivos.append(error)
            elif creada:
                categoria_creada = categoria.name
            else:
                categoria_reusada = categoria.name
    elif not motivos and datos['categoria']:
        categoria = Category.objects.filter(
            name__iexact=datos['categoria'],
        ).first()

    # --------------------- 1. la puerta ------------------------------
    if motivos:
        envio = _registrar(
            colaborador, 'rechazado', datos, motivos, [], ficha, request,
        )
        return Response(
            {'estado': 'rechazado', 'motivos': motivos, 'faltan': [],
             'recibo': envio.id},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ------------------ 2. completar la ficha elegida -----------------
    if ficha is not None:
        completado = validacion.enriquecer(ficha, datos, categoria=categoria)
        _guardar_imagenes(ficha, archivos)
        # Releer: `enriquecer` dejo en la instancia la cache de "no tiene
        # contacto" de antes de crearlo, y con ella `cumple_obligatorios`
        # veria el telefono que acaba de ponerse.
        ficha = Business.objects.get(pk=ficha.pk)
        # Siempre, no solo si acaba de tocar algo: puede que ya cumpliera
        # los obligatorios desde antes y se quedara esperando.
        pendientes.publicar_si_cumple(
            [ficha], PublicationStatus.objects.get(slug='publicado'),
        )
        ficha = Business.objects.get(pk=ficha.pk)
        faltan = pendientes.faltantes_de(ficha)
        # El estado es el de la ficha DESPUES, no "lo que se acaba de
        # promover": una ficha ya publicada sigue publicada aunque solo
        # se le complete la descripcion.
        estado = (
            'publicado'
            if ficha.publication_status.slug == 'publicado'
            else 'pendiente'
        )
        envio = _registrar(
            colaborador, estado, datos, [], faltan, ficha, request,
        )
        return Response({
            'estado': estado,
            'motivos': [],
            'faltan': faltan,
            'completado': completado,
            'recibo': envio.id,
            'imagenes': ficha.images.count(),
            'categoria_creada': categoria_creada,
            'categoria_reusada': categoria_reusada,
        })

    # --------------------- 3. el cruce -------------------------------
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
        # El techo de 5 tambien aqui: en la puerta no se sabia cuantas
        # traia la ficha que el cruce acaba de encontrar.
        if (existente.images.count() + len(archivos)
                > MAX_IMAGES_PER_BUSINESS):
            motivo = 'Se aceptan hasta 5 imagenes por ficha.'
            envio = _registrar(
                colaborador, 'rechazado', datos, [motivo], [],
                existente, request,
            )
            return Response(
                {'estado': 'rechazado', 'motivos': [motivo],
                 'faltan': [], 'recibo': envio.id},
                status=status.HTTP_400_BAD_REQUEST,
            )
        completado = validacion.enriquecer(existente, datos, categoria=categoria)
        _guardar_imagenes(existente, archivos)
        # Releer: `enriquecer` dejo en la instancia la cache de "no tiene
        # contacto" de antes de crearlo, y con ella `cumple_obligatorios`
        # veria el telefono que acaba de ponerse. Sin releer, la ficha se
        # quedaria en revision a pesar de que ya cumple los obligatorios.
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
            'imagenes': existente.images.count(),
            'categoria_creada': categoria_creada,
            'categoria_reusada': categoria_reusada,
        })

    # ------------------- 4. entrar y publicar ------------------------
    negocio = ingreso.crear(
        datos,
        categoria=categoria,
        en_revision=PublicationStatus.objects.get(slug='en-revision'),
        procedencia='levantado',
    )
    _guardar_imagenes(negocio, archivos)
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
         'recibo': envio.id, 'imagenes': negocio.images.count(),
         'categoria_creada': categoria_creada,
         'categoria_reusada': categoria_reusada},
        status=status.HTTP_201_CREATED,
    )
