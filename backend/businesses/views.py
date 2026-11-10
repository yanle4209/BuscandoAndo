from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone

# El mapa (radio de R1, cabeceras, distancia) vive en su modulo: si
# estuviera aqui, el importador tendria que importar ``views`` y se
# crearia un ciclo. Se importa el paquete ademas de los nombres sueltos
# porque la vista ``cabeceras`` taparia al ``cabeceras`` del modulo.
from .firma import colaborador_de, token_de
from . import busqueda
from . import geografia
from .geografia import (
    RADIO_KM,
    SIN_MUNICIPIO,
    cabecera_para,
    haversine_distance,
    normalizar,
)
from .models import Business, Correction, SlugAntiguo, Pospuesto
from business_locations.models import BusinessLocation
from .serializers import BusinessListSerializer, BusinessDetailSerializer, CorrectionCreateSerializer, CorrectionSerializer

# Las metricas de uso se cuentan dentro de la vista que ya atiende la
# peticion (uso.models): aqui solo se le avisa.
from uso.models import registrar

# Se traen los nombres sueltos y no el modulo: la vista se llama
# ``pendientes`` igual que el modulo, y dentro de la funcion el nombre
# local taparia al importado.
from .pendientes import (
    ETIQUETAS as ETIQUETAS_PENDIENTES,
    con_trabajo,
    contar_pendientes,
    faltantes_de,
    particionar,
)


def is_featured_active(biz):
    """Check if a business's featured status is still active."""
    if not biz.is_featured:
        return False
    if biz.featured_permanent:
        return True
    if biz.featured_end_date and biz.featured_end_date < timezone.now():
        return False
    return True


class FeaturedPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'


class SearchPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'


def parse_radio(valor):
    """Radio solicitado, siempre acotado a RADIO_KM.

    Antes el codigo hacia ``float(params.get('radius', 10))`` sin comprobar
    nada, y lo calculaba aunque no hubiera coordenadas: un ``?radius=abc``
    devolvia un 500. Aqui cualquier no numerico (o un radio negativo) cae en
    el valor por defecto y lo que supere el tope se recorta.
    """
    try:
        pedido = float(valor)
    except (TypeError, ValueError):
        return RADIO_KM
    if pedido <= 0:
        return RADIO_KM
    return min(pedido, RADIO_KM)


def negocios_en_radio(qs, lat, lng, radius_km):
    """Recorta ``qs`` a los negocios a ``radius_km`` o menos del punto.

    Haversine en Python, igual que ya se hacia: no hay PostGIS en el
    proyecto y con el volumen actual no hace falta. Los negocios sin
    ubicacion y con coordenadas invalidas quedan fuera del radio, que es
    lo que quiere R1 (sin punto no hay cercania que calcular).
    """
    try:
        user_lat = float(lat)
        user_lng = float(lng)
    except (TypeError, ValueError):
        return qs

    # Solo hacen falta el id y las coordenadas. El queryset que llega
    # trae prefetch de location, contact, hours e images (para pintar las
    # 12 fichas de la pagina), pero recorrerlo tal cual cargaba esas
    # relaciones de TODOS los negocios solo para medir el radio: ~0,6 s
    # medidos en produccion con 738 fichas, y era el coste dominante del
    # buscador. Mismo patron que ``busqueda.filtrar_por_texto``.
    filas = qs.prefetch_related(None).values_list(
        'id', 'location__latitude', 'location__longitude'
    )

    dentro = []
    for biz_id, biz_lat, biz_lng in filas:
        if biz_lat is None or biz_lng is None:
            continue
        if haversine_distance(
            user_lat, user_lng, float(biz_lat), float(biz_lng)
        ) <= radius_km:
            dentro.append(biz_id)

    return qs.filter(id__in=dentro)


class CorrectionViewSet(viewsets.ModelViewSet):
    """Avisos de datos incorrectos (boton "Corregir" del frontend).

    POST /api/corrections/ -> PUBLICO: es un formulario abierto a cualquier
    visitante, sin login.

    Todo lo demas (list, retrieve, update, destroy) -> solo staff. Ahi
    estan los avisos de otros usuarios y las notas internas del admin, y
    sin este override saldria publico: el DEFAULT_PERMISSION_CLASSES del
    proyecto es AllowAny (ver config/settings.py).
    """

    queryset = Correction.objects.select_related('business').all()

    def _accion_en_ejecucion(self):
        """La accion que esta atendiendo esta peticion ('create', 'list'...).

        No se puede usar ``self.action`` a secas: ViewSetMixin lo asigna
        DESPUES de llamar a super().initialize_request(), y es justo ahi
        dentro donde DRF construye los autenticadores. A ese punto si ya
        estan ``self.action_map`` y ``self.request`` (el request Django
        crudo), que el ``view()`` del router pone antes de llamar a
        dispatch() — ver rest_framework/viewsets.py, as_view().
        """
        if hasattr(self, 'action'):
            return self.action
        request = getattr(self, 'request', None)
        if request is None:
            return None
        return getattr(self, 'action_map', {}).get(request.method.lower())

    def get_authenticators(self):
        """El POST publico va SIN autenticadores.

        DRF usa SessionAuthentication por defecto. Si quien envia el
        formulario tiene la sesion del admin abierta en el mismo dominio,
        esa clase le exige token CSRF y el envio devolveria 403. Al ser
        un endpoint AllowAny, no hacerse pasar por nadie es ademas lo
        correcto. El listado y el resto siguen autenticando con normalidad.
        """
        if self._accion_en_ejecucion() == 'create':
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self._accion_en_ejecucion() == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'create':
            return CorrectionCreateSerializer
        return CorrectionSerializer

    def perform_create(self, serializer):
        """El aviso entra y de paso se cuenta, sin frenar el formulario."""
        super().perform_create(serializer)
        registrar('correccion', self.request)


class BusinessViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API publica de negocios.
    Solo muestra negocios PUBLICADOS.
    Soporta busqueda por radio (5km).
    """
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BusinessDetailSerializer
        return BusinessListSerializer

    def get_pagination_class(self):
        if self.request.query_params.get('featured') == 'true':
            return FeaturedPagination
        return SearchPagination

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            pagination_class = self.get_pagination_class()
            if pagination_class and self.request and self.request.query_params.get('format') != 'api':
                self._paginator = pagination_class()
            else:
                self._paginator = None
        return self._paginator

    def get_queryset(self):
        qs = Business.objects.filter(
            publication_status__slug='publicado'
        ).select_related(
            'category', 'publication_status', 'operational_status'
        ).prefetch_related('location', 'contact', 'hours', 'images')

        # Fase geografica (DISENO.md FASE1): listado y ficha recortan a
        # las provincias de fase. Nada se borra: lo de fuera sigue en la
        # base y el admin lo ve, pero la web no lo sirve ni por enlace
        # directo.
        qs = qs.filter(geografia.q_fase())

        params = self.request.query_params

        # Busqueda por texto: no aqui, al FINAL, una vez aplicados el
        # radio y los demas filtros (ver ``busqueda.filtrar_por_texto``).

        # Filtrar por categoria
        category = params.get('category')
        if category:
            try:
                qs = qs.filter(category__id=int(category))
            except (ValueError, TypeError):
                qs = qs.filter(category__slug=category)

        # `city` NO es filtro (R3.5): la ciudad ya es coordenadas + 5 km.
        # Un filtro por nombre seria un segundo radio encubierto. Si un
        # cliente con el JS viejo lo sigue mandando, se ignora.
        # Ver FiltroCityTests.

        # Filtrar por estado operativo
        op_status = params.get('operational_status')
        if op_status:
            qs = qs.filter(operational_status__slug=op_status)

        # Solo destacados (filter out expired)
        featured = params.get('featured')
        if featured == 'true':
            now = timezone.now()
            qs = qs.filter(
                is_featured=True,
            ).filter(
                Q(featured_permanent=True) |
                Q(featured_end_date__isnull=True) |
                Q(featured_end_date__gt=now)
            )
            # Ordenar por nivel: '1' = principal ... '4' = basico.
            # OJO: hay que ordenar el QuerySet. Si se ordena una lista y luego se
            # reconstruye con filter(id__in=...), Django vuelve a aplicar
            # Meta.ordering ('-is_featured', '-created_at') y el orden se pierde.
            tier_order = {'1': 0, '2': 1, '3': 2, '4': 3}
            qs = qs.annotate(
                tier_ord=Case(
                    *[When(featured_tier=tier, then=Value(pos))
                      for tier, pos in tier_order.items()],
                    default=Value(len(tier_order)),
                    output_field=IntegerField(),
                )
            ).order_by('tier_ord', '-created_at')

        # Filtrar por radio. R1: unica y exclusivamente a RADIO_KM del punto
        # activo del usuario. Sin coordenadas no hay radio que aplicar (y el
        # frontend no deberia consultar sin punto activo: DISENO.md R1.1).
        lat = params.get('lat')
        lng = params.get('lng')
        if lat and lng:
            qs = negocios_en_radio(qs, lat, lng, parse_radio(params.get('radius')))

        # Busqueda por texto. Mismos campos que featured_by_search: si los
        # destacados buscan en la categoria y el listado no, "restaurante"
        # enseña 2 destacados sobre "0 resultados" (lo contrario de que
        # siempre haya resultados si estan disponibles).
        #
        # Va la ULTIMA porque se puntua en Python (SQL no distingue tildes
        # ni erratas): el recorte en memoria se paga sobre lo que ya pasa
        # el radio, no sobre la base entera.
        search = params.get('text') or params.get('search')
        if search:
            qs = busqueda.filtrar_por_texto(qs, search)

        return qs

    def list(self, request, *args, **kwargs):
        """La consulta del buscador, y de paso su cuenta en las metricas.

        El texto tecleado y el numero de resultados viajan juntos: es
        lo que dice que buscan y si lo encuentran. Los destacados NO
        cuentan (``featured-by-search``): el frontend dispara las dos
        llamadas en la misma accion de buscar, y contar las dos seria
        cobrar dos veces por un mismo clic.
        """
        respuesta = super().list(request, *args, **kwargs)
        termino = (request.query_params.get('text')
                   or request.query_params.get('search') or '')
        resultados = None
        if isinstance(respuesta.data, dict):
            resultados = len(respuesta.data.get('results') or [])
        elif isinstance(respuesta.data, list):
            resultados = len(respuesta.data)

        # Fase geografica: una busqueda SIN municipio de fase cerca se
        # cuenta como fuera_zona (y con su lugar: ese es el mapa de la
        # demanda que decide donde abrir despues), no como consulta.
        # El termino se cuenta igual — que buscan los de fuera tambien
        # interesa — pero SIN resultados: los 0 de fuera no ensucian la
        # lista de "lo que falta levantar" (metrica interna).
        evento = 'consulta'
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
        except (TypeError, ValueError):
            lat = lng = None
        if lat is not None and not geografia.punto_en_fase(lat, lng):
            evento = 'fuera_zona'
        registrar(evento, request,
                  termino=termino or None,
                  resultados=None if evento == 'fuera_zona' else resultados)
        return respuesta

    def retrieve(self, request, *args, **kwargs):
        """Abrir una ficha tambien se cuenta: es la pagina que importa.

        Si piden un slug que el negocio tuvo ANTES de cambiarlo, la API
        redirige 301 al slug actual (SlugAntiguo) en vez de dar 404:
        misma regla que la vista publica. Lo no publicado o fuera de
        fase sigue siendo 404 — se comprueba aqui igual que en el
        queryset, para no filtrar nada de lo que no se ensena. En la
        redireccion no se cuenta la visita: la peticion de despues (con
        el slug bueno) la cuenta, y sin eso se contaria dos veces.
        """
        try:
            respuesta = super().retrieve(request, *args, **kwargs)
        except Http404:
            origen = self.kwargs.get(self.lookup_field) or ''
            destino = None
            if origen:
                destino = (
                    SlugAntiguo.objects
                    .filter(slug=origen,
                            business__publication_status__slug='publicado')
                    .filter(geografia.q_fase('business__'))
                    .values_list('business__slug', flat=True)
                    .first()
                )
            if not destino or destino == origen:
                raise
            return redirect('business-detail', slug=destino, permanent=True)
        registrar('ficha', request)
        return respuesta

    @action(detail=False, methods=['get'], url_path='featured-by-search')
    def featured_by_search(self, request):
        """Devuelve hasta 3 destacados activos que coincidan con la busqueda.

        Se recorren los niveles del 1 (principal) al 4 (basico), de modo que
        siempre entra el mejor nivel disponible. Los niveles son los que define
        ``Business.FEATURED_TIERS``: '1'..'4' (nunca 'large'/'medium'/'small').
        """
        params = request.query_params
        search = params.get('text') or params.get('search')
        category = params.get('category')

        now = timezone.now()
        qs = Business.objects.filter(
            publication_status__slug='publicado',
            is_featured=True,
        ).filter(
            Q(featured_permanent=True) |
            Q(featured_end_date__isnull=True) |
            Q(featured_end_date__gt=now)
        ).filter(
            # Fase geografica: los destacados del buscador recortan igual
            # que el listado (estan sobre "0 resultados" si no).
            geografia.q_fase()
        ).select_related(
            'category', 'publication_status', 'operational_status'
        ).prefetch_related('location', 'contact', 'hours', 'images')

        # Busqueda por texto: NO aqui, al FINAL (ver mas abajo).

        # Filter by category if provided
        if category:
            try:
                qs = qs.filter(category__id=int(category))
            except (ValueError, TypeError):
                qs = qs.filter(category__slug=category)

        # R3.5: `city` tampoco aqui. Ver FiltroCityTests.

        # R1.2: los destacados del buscador entran en el MISMO filtro de 5 km
        # que los resultados normales. Sin coordenadas no se recorta (y sin
        # busqueda no hay fila que devolver, que es la regla de abajo).
        lat = params.get('lat')
        lng = params.get('lng')
        if lat and lng:
            qs = negocios_en_radio(qs, lat, lng, parse_radio(params.get('radius')))

        # Busqueda por texto, con los MISMOS criterios que el listado: si los
        # destacados buscan distinto, "restaurante" enseña 2 destacados sobre
        # "0 resultados" (lo contrario de que siempre haya resultados si estan
        # disponibles). Se puntua en Python (sin tildes, con erratas) y, como
        # en el listado, va despues del radio para no puntuar la base entera.
        if search:
            qs = busqueda.filtrar_por_texto(qs, search)

        # If no search filters, return empty
        if not search and not category:
            return Response([])

        # Escoger hasta 3 destacados, del mejor nivel al peor (1 -> 4).
        # El queryset ya esta filtrado por is_featured=True y por no expirado.
        result = []
        for tier in ['1', '2', '3', '4']:
            if len(result) >= 3:
                break
            biz = qs.filter(featured_tier=tier).first()
            if biz:
                result.append(biz)

        serializer = BusinessListSerializer(result, many=True)
        return Response(serializer.data)


@api_view(['GET'])
def cabeceras(request):
    """Las cabeceras municipales de las provincias de fase (FASE1).

    Un dato, dos usos (DISENO.md R3):

    * ancla del circulo de 5 km cuando el usuario no da su ubicacion, y
    * fuente del selector manual de municipio.

    La fase geografica recorta AQUI: el padron completo (158) sigue en
    ``geografia.cabeceras()`` y lo usan el admin, el importador y el
    reporte de pendientes. Web, app y levantamiento leen este mismo
    endpoint, asi que los tres quedan recortados de una sola vez. Sin
    provincias de fase configuradas se devuelven las 158.

    Se devuelve una lista plana agrupable por el cliente: la agrupacion por
    provincia es cosa de la interfaz, no del API.
    """
    return Response(geografia.cabeceras_en_fase())


@api_view(['POST'])
def interes(request):
    """Aviso de lista de espera de la fase geografica.

    El boton del banner de "todavia no llegamos a tu zona" suma UNA vez
    el interes del punto (metrica ``aviso_interes``): el admin la ve en
    el panel de uso, contada por municipio/provincia, y es lo que decide
    donde abrir despues.

    No se guarda NADA del usuario — ni correo, ni cookies, ni IP: es el
    mismo contador agregado de siempre (dia x evento x lugar x
    plataforma), asi que el endpoint no puede ser una fuga de datos ni
    una lista que haya que limpiar. El lugar sale del ``lat``/``lng`` de
    la query, como en el resto del API.
    """
    registrar('aviso_interes', request)
    return Response({'ok': True})


def _provincia_de(grupo):
    """La provincia de la primera ficha que la traiga. Texto libre en la
    base, asi que se lee de los datos y no se adivina."""
    for b in grupo:
        loc = getattr(b, 'location', None)
        if loc is not None and loc.province:
            return loc.province
    return ''


def _fila(nombre, grupo, provincia='', pospuestos=frozenset()):
    """Una fila del listado: el trabajo que hay en un municipio.

    Los DOS contadores cuentan exactamente lo que luego sale en el
    detalle (``particionar``): ``con_revision`` de la lista principal y
    ``con_publicadas`` de la lista aparte. Asi la fila promete N y la
    lista entrega N.

    ``pospuestos`` son los ids que este dueno decidio dejar aparte: se
    descuentan de los contadores (siguen en ``total``, que son fichas
    del municipio) para que fila, boton y lista digan lo mismo, y el
    ``con_pospuestos`` abre el detalle aunque ya no quede nada mas.
    """
    trabajo = [b for b in grupo if b.id not in pospuestos]
    cubos = particionar(trabajo)
    return {
        'municipio': nombre,
        'provincia': provincia,
        'total': len(grupo),
        'con_revision': len(cubos['revision']),
        'con_publicadas': len(cubos['publicadas']),
        'en_revision': sum(
            1 for b in trabajo if b.publication_status.slug != 'publicado'
        ),
        'con_pospuestos': sum(
            1 for b in grupo
            if b.id in pospuestos and con_trabajo(b)
        ),
    }


# El casillero de las fichas SIN categoria en el filtro del reporte: un
# slug vacio no sirve porque tambien es «todas las categorias».
SIN_CATEGORIA = 'sin-categoria'


def _es_de_categoria(biz, categoria):
    """Pasa el filtro del desplegable (``?categoria=``). Vacio = todo."""
    if not categoria:
        return True
    if categoria == SIN_CATEGORIA:
        return biz.category_id is None
    return biz.category_id is not None and biz.category.slug == categoria


def _solo_categoria(cubos, categoria):
    """El mismo reparto, con el filtro aplicado a los tres cubos."""
    if not categoria:
        return cubos
    return {
        clave: [par for par in lista if _es_de_categoria(par[0], categoria)]
        for clave, lista in cubos.items()
    }


def _categorias_de(cubos):
    """Lo que hay que tocar, categoria a categoria, para el filtro.

    El desglose sale del MISMO reparto que las listas: asi el numero
    del desplegable y el de la lista son siempre el mismo. Solo las
    categorias con trabajo —las vacias no estorban en el desplegable—.
    """
    conteo = {}
    for clave, campo in (('revision', 'con_revision'),
                         ('publicadas', 'con_publicadas')):
        for biz, _ in cubos[clave]:
            slug = biz.category.slug if biz.category_id else SIN_CATEGORIA
            fila = conteo.setdefault(slug, {
                'slug': slug,
                'nombre': (biz.category.name if biz.category_id
                           else '(sin categoría)'),
                'con_revision': 0,
                'con_publicadas': 0,
            })
            fila[campo] += 1
    return sorted(conteo.values(), key=lambda c: c['nombre'].casefold())


def _le_toca(colaborador, municipio):
    """§11-i: al colaborador le toca SU municipio, y solo el suyo.

    Se compara normalizado porque el nombre de ``Colaborador.municipio``
    lo teclea el admin y el del reporte viene de texto libre: 'Bani' y
    'Baní' son el mismo municipio.
    """
    asignado = (colaborador.municipio or '').strip()
    return bool(asignado) and normalizar(asignado) == normalizar(municipio)


def _acceso_reporte(request):
    """Quien puede leer o mover el reporte de §11.1.

    Devuelve ``(colaborador, usuario, error)``: el colaborador que firma
    con su token, el usuario admin de la sesion (``None`` si no lo es) y
    la respuesta de error para quien no es ninguno de los dos. La misma
    puerta para el GET del reporte y el POST de posponer: si cada uno
    abriera la suya, posponer serviria a quien no puede ni leer.

    El TOKEN manda sobre la sesion: quien lo trae esta declarando «soy
    este colaborador», y en este mismo navegador puede haber ademas una
    sesion de admin abierta —sin eso, el navegador se quedaba con el
    primer municipio de la lista entera (Azua) diciendole al dueño del
    token que su municipio era ese. Sin token manda la sesion de admin
    (la lista entera); sin ninguna de las dos, 403.
    """
    colaborador = colaborador_de(request)

    if colaborador is None and token_de(request):
        # Quien manda un token que no vale (o que esta apagado) no es lo
        # mismo que quien no manda nada: el primero puede arreglarlo.
        return None, None, Response(
            {'detail': 'Token de colaborador invalido o inactivo.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    usuario = getattr(request, 'user', None)
    es_admin = bool(
        usuario is not None and usuario.is_authenticated and usuario.is_staff
    )

    if colaborador is None and not es_admin:
        return None, None, Response(
            {'detail': 'Sesion de administrador o token de colaborador.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    return colaborador, (usuario if es_admin else None), None


def _pospuestos_de(colaborador, usuario):
    """Los ids de las fichas que este dueno decidio dejar aparte.

    Un conjunto para descontarlos de un listado entero —o de las 158
    filas del padron— sin una consulta por municipio. Quien no es
    nadie no pospone nada.
    """
    if colaborador is not None:
        base = Pospuesto.objects.filter(colaborador=colaborador)
    elif usuario is not None:
        base = Pospuesto.objects.filter(usuario=usuario)
    else:
        return frozenset()
    return frozenset(base.values_list('negocio_id', flat=True))


def _para_formulario(biz):
    """La ficha entera, en la forma que espera el formulario (Fase D).

    El listado de ``fichas`` trae solo lo justo para decir QUÉ falta; el
    formulario necesita ademas lo que YA hay —telefono, calle, horario—
    para salir rellenado. Pedirselo a los 148 de golpe seria mandar medio
    municipio a rellenar UNO, y por eso esto va aparte, uno a uno.
    """
    from business_hours.models import BusinessHours

    loc = getattr(biz, 'location', None)
    contact = getattr(biz, 'contact', None)

    municipio = (getattr(loc, 'municipality', '') or '') if loc else ''
    dias = {valor: nombre for valor, nombre in BusinessHours.DayOfWeek.choices}
    horario = [
        {'dia': dias.get(h.day, h.day),
         'desde': h.open_time.isoformat()[:5] if h.open_time else '',
         'hasta': h.close_time.isoformat()[:5] if h.close_time else ''}
        for h in biz.hours.all()
        if not h.is_closed and h.open_time and h.close_time
    ]

    return {
        'id': biz.id,
        'nombre': biz.name or '',
        'slug': biz.slug,
        'estado': biz.publication_status.slug,
        'procedencia': biz.procedencia,
        'categoria': biz.category.name if biz.category_id else '',
        'descripcion': biz.description or '',
        'operativo': (
            biz.operational_status.slug if biz.operational_status_id else ''
        ),
        'calle': (loc.street or '') if loc else '',
        'sector': (loc.sector or '') if loc else '',
        'referencias': (loc.referencias or '') if loc else '',
        'municipio': municipio,
        'provincia': (loc.province or '') if loc else '',
        'lat': loc.latitude if loc else None,
        'lng': loc.longitude if loc else None,
        'telefono': (contact.phone or '') if contact else '',
        'whatsapp': (contact.whatsapp or '') if contact else '',
        'correo': (contact.email or '') if contact else '',
        'web': (contact.website or '') if contact else '',
        'horario': horario,
        # Cuantas fotos tiene YA: con ese numero el formulario calcula
        # cuanto le queda de las 5 que caben, sin tener que mandarlas.
        'imagenes': biz.images.count(),
        'faltan': faltantes_de(biz),
    }


def _una_ficha(colaborador, ficha_id):
    """La respuesta de ``?ficha=``: una sola ficha, o el motivo por el
    que no se puede dar."""
    try:
        pk = int(ficha_id)
    except (TypeError, ValueError):
        return Response(
            {'detail': '"ficha" tiene que ser un numero.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ficha = (
        Business.objects
        .select_related(
            'location', 'contact', 'category', 'operational_status',
            'publication_status',
        )
        # `hours` e `images` entran en `faltantes_de` (la foto es
        # obligatoria): sin precargar, la ficha cuesta una consulta por
        # cada una de las dos.
        .prefetch_related('hours', 'images')
        .filter(pk=pk)
        .first()
    )
    if ficha is None:
        return Response(
            {'detail': 'Esa ficha no existe.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    loc = getattr(ficha, 'location', None)
    municipio = (getattr(loc, 'municipality', '') or '') if loc else ''
    if colaborador is not None and not _le_toca(colaborador, municipio):
        # §11-i: el reporte le da la lista de SU municipio, y con esta
        # misma llave no se abre otra.
        return Response(
            {'detail': 'A este token le toca otro municipio.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(_para_formulario(ficha))


def _variantes_de(nombre):
    """Los nombres guardados en la base que SON este municipio.

    El cruce del reporte es por ``normalizar`` —"Baní" y "Bani" son el
    mismo sitio—, y esa regla vive en Python. Aqui se aplica la MISMA
    regla a la lista corta de municipios distintos que hay en la base
    (un ``DISTINCT`` sobre la columna, que desde la migracion de indices
    es una pasada por el indice) para poder filtrar en SQL: el grupo que
    queda es exactamente el que despues se agruparia, pero sin traer las
    16 mil fichas del pais para quedarse con las de un municipio.
    """
    objetivo = normalizar(nombre)
    if not objetivo:
        return []
    guardados = (
        BusinessLocation.objects
        .exclude(municipality__isnull=True)
        .exclude(municipality='')
        .values_list('municipality', flat=True)
        .distinct()
    )
    return [m for m in guardados if normalizar(m) == objetivo]


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def pendientes(request):
    """Reporte de pendientes por municipio (DISENO.md seccion 11.1).

    La ficha de trabajo del editor. Sin ``?municipio=`` lista **todos los
    municipios del padron** —con cuantas hay en revision y cuantas
    publicadas traen faltantes— para elegir donde trabajar; con el
    parametro, el detalle de ese municipio, agrupado por campo faltante.

    **Dos listas, cubos disjuntos** (``pendientes.particionar``). En la
    de REVISION entra todo lo que le falta un **obligatorio** —aunque
    este publicada— y lo que todavia no se publica: ahi se completa y se
    publica. En la de PUBLICADAS entran las ya publicadas con todos los
    obligatorios y aun opcionales sin completar: salen aparte para
    rellenarlas mas adelante, sin estorbar la lista principal.

    Con ``?categoria=`` el detalle se limita a esa categoria —su slug,
    o el casillero ``sin-categoria``— y cada respuesta trae el desglose
    ``categorias`` para el desplegable, medido con el MISMO reparto que
    las listas. Los **pospuestos** —lo que el editor decidio no
    completar— salen de las listas y de los contadores y vuelven en su
    propia lista ``pospuestos``; el POST ``/api/pospuesto/`` es quien
    los mueve.

    Este GET **no guarda nada nuevo**: el municipio lo da
    la ubicacion de cada ficha, la cabecera viene del CSV de la seccion 9
    y el circulo, del radio de R1. Por eso no hace falta ampliar el
    serializer de lista con ``hours[]``: el horario se cuenta aqui, en el
    servidor, en vez de pedir 325 llamadas de detalle (pendiente *i*).

    **Quien lo lee** (§11-i): el admin, todo; el colaborador, solo el
    municipio que le esta asignado y firmado con su token —el suyo es el
    que le dice que hacer—. Sin eso el reporte seria una puerta trasera a
    las fichas sin publicar.

    El listado sale del **padron de las 158 cabeceras**, no de lo que ya
    tenga fichas: un municipio todavia sin importar aparece con
    ``total: 0``, que es exactamente el trabajo que falta.
    """
    municipio = (request.query_params.get('municipio') or '').strip()
    # El filtro del desplegable: slug de categoria, el casillero de las
    # sin-categoria, o vacio (= todas).
    categoria = (request.query_params.get('categoria') or '').strip()

    # ---------------------------- quien pregunta ----------------------
    # La misma puerta que el POST de posponer (si cada uno abriera la
    # suya, posponer serviria a quien no puede ni leer).
    colaborador, usuario, error = _acceso_reporte(request)
    if error is not None:
        return error

    # Los que este dueno dejo aparte: salen de las listas de trabajo y
    # de los contadores de SU reporte, pero siguen en `total`.
    pospuestos = _pospuestos_de(colaborador, usuario)

    # Una ficha concreta, para POBLAR el formulario: va primero porque
    # conoce su propio municipio y no hace falta que se lo pidan.
    ficha_id = (request.query_params.get('ficha') or '').strip()
    if ficha_id:
        return _una_ficha(colaborador, ficha_id)

    if (colaborador is not None and municipio
            and not _le_toca(colaborador, municipio)):
        # §11-i: "ni reportes ajenos". Un token no sirve para mirar el
        # municipio de otro, que es lo unico que esta en el reporte.
        return Response(
            {'detail': 'A este token le toca otro municipio.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # El reporte de UN municipio no necesita las 16 mil fichas del pais:
    # ni el renglon del token ni el detalle se fijan en otra. Antes se
    # cargaba TODO y se agrupaba en Python para quedarse con un grupo
    # (~2 s por peticion en local; en produccion el gesto de posponer
    # —tres peticiones— se comia unos 15 s). Solo la lista entera del
    # padron (admin, sin municipio) sigue necesitando el escaneo
    # completo. `None` = sin acotar.
    alcance = None
    if municipio:
        # "(sin municipio)" es el grupo de las fichas SIN ubicacion:
        # no se acota para no cambiar el significado de ese parametro.
        if normalizar(municipio) != normalizar(SIN_MUNICIPIO):
            alcance = _variantes_de(municipio)
    elif colaborador is not None:
        # El renglon: solo las fichas de SU municipio. Sin municipio
        # asignado el alcance queda vacio y mas abajo se devuelve el
        # 400 de siempre, sin haber cargado nada.
        alcance = _variantes_de(colaborador.municipio)

    negocios = (
        Business.objects
        .select_related('location', 'contact', 'category', 'publication_status')
        # `images` porque la foto es obligatoria y `faltantes_de` la
        # mira: sin precargar, una consulta por ficha.
        .prefetch_related('hours', 'images')
    )
    if alcance is not None:
        # INNER JOIN: las fichas sin ubicacion no son de NINGUN
        # municipio, asi que no pertenecian al grupo pedido tampoco.
        negocios = negocios.filter(location__municipality__in=alcance)

    grupos = {}
    indice = {}
    for biz in negocios:
        loc = getattr(biz, 'location', None)
        nombre = ((loc.municipality if loc else '') or '').strip()
        nombre = nombre or SIN_MUNICIPIO
        grupos.setdefault(nombre, []).append(biz)
        indice.setdefault(normalizar(nombre), nombre)

    padron = geografia.cabeceras()
    grupos_por_norma = {normalizar(k): v for k, v in grupos.items()}

    if not municipio:
        # Al colaborador no le sale la lista entera: su renglon es el
        # unico que le toca (§11-i). Sin municipio asignado no hay nada
        # que enseñarle, y eso no es culpa suya — es un reparto que
        # todavia no se ha hecho.
        if colaborador is not None:
            asignado = (colaborador.municipio or '').strip()
            if not asignado:
                return Response(
                    {'detail': 'Este token no tiene municipio asignado.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            clave = normalizar(asignado)
            en_padron = next(
                (c for c in padron if normalizar(c['municipio']) == clave),
                None,
            )
            nombre = en_padron['municipio'] if en_padron else asignado
            provincia = (
                en_padron['provincia'] if en_padron
                else _provincia_de(grupos_por_norma.get(clave, []))
            )
            fila = _fila(
                nombre, grupos_por_norma.get(clave, []), provincia,
                pospuestos,
            )
            # Quien firma este renglon. Solo aqui: la lista entera del admin
            # no viene de un token y por lo tanto no trae nombre de nadie.
            # Lo ve unicamente quien ya tiene el token, que es ese
            # colaborador — no se abre nada nuevo.
            fila['colaborador'] = colaborador.nombre
            return Response([fila])

        # El listado es del PADRÓN, no de lo que ya tenga fichas: un
        # municipio sin importar sale con total 0, que es justamente el
        # trabajo que falta (los 157 restantes hoy).
        filas = []
        claves_del_padron = set()
        for cab in padron:
            clave = normalizar(cab['municipio'])
            claves_del_padron.add(clave)
            filas.append(
                _fila(
                    cab['municipio'],
                    grupos_por_norma.get(clave, []),
                    cab['provincia'],
                    pospuestos,
                )
            )

        # Lo que no casa con ninguna cabecera —incluidas las fichas sin
        # municipio— tampoco se puede perder: no poder asignarlas es
        # justo algo que hay que ver.
        for nombre, grupo in grupos.items():
            if normalizar(nombre) not in claves_del_padron:
                filas.append(
                    _fila(nombre, grupo, _provincia_de(grupo), pospuestos),
                )

        filas.sort(key=lambda f: (f['provincia'].casefold(),
                                  f['municipio'].casefold()))
        return Response(filas)

    real = indice.get(normalizar(municipio))
    grupo = grupos.get(real, []) if real else []
    provincia = _provincia_de(grupo)
    cab = cabecera_para(real, provincia) if real else None

    if real is None:
        # Un municipio del padron sin fichas NO es un error: es el
        # reporte de un sitio donde todavia no ha entrado nada, que es
        # exactamente lo que un colaborador tiene que poder ver antes de
        # salir a levantar. El 404 se reserva para el nombre que no es de
        # ningun municipio del pais.
        en_padron = next(
            (c for c in padron
             if normalizar(c['municipio']) == normalizar(municipio)),
            None,
        )
        if en_padron is None:
            return Response(
                {'detail': 'No hay ni fichas ni municipio llamado "%s".'
                           % municipio},
                status=status.HTTP_404_NOT_FOUND,
            )
        real = en_padron['municipio']
        provincia = en_padron['provincia']
        cab = en_padron

    # Dos listas, cubos disjuntos (particionar): en REVISION entra lo
    # que le falta un obligatorio —aunque este publicada— y lo que
    # todavia no se publica; en PUBLICADAS, las que ya estan publicadas
    # con todos los obligatorios y solo traen opcionales sin completar.
    # El editor pidio tenerlas aparte, en la misma tarjeta, para
    # rellenarlas mas adelante sin estorbar la lista principal.
    # Los POSPUESTOS no son trabajo: salen del reparto (siguen en
    # `total`, que son fichas del municipio) y vuelven en su propia
    # lista de la misma tarjeta.
    trabajo = [b for b in grupo if b.id not in pospuestos]

    # Un SOLO reparto: de ahi sale el desglose por categoria del filtro
    # y, con el filtro aplicado, las dos listas — asi el numero del
    # desplegable y el de la lista son siempre el mismo.
    cubos = particionar(trabajo)
    categorias = _categorias_de(cubos)
    if categoria and not any(c['slug'] == categoria for c in categorias):
        # La categoria elegida puede quedarse sin trabajo (todo
        # completado o pospuesto): el desplegable tiene que seguirla
        # ofreciendo, o su valor actual desapareceria de las opciones y
        # el select se quedaria en blanco.
        nombre = next(
            (b.category.name for b in grupo
             if b.category_id and b.category.slug == categoria),
            None,
        )
        if categoria == SIN_CATEGORIA:
            nombre = '(sin categoría)'
        categorias.append({
            'slug': categoria,
            'nombre': nombre or categoria,
            'con_revision': 0,
            'con_publicadas': 0,
        })
        categorias.sort(key=lambda c: c['nombre'].casefold())
    cubos = _solo_categoria(cubos, categoria)

    def _detalle_ficha(par):
        b, faltan = par
        return {
            'id': b.id,
            'nombre': b.name,
            'slug': b.slug,
            'estado': b.publication_status.slug,
            'procedencia': b.procedencia,
            'categoria': b.category.name if b.category_id else None,
            'lat': (getattr(b, 'location', None).lat
                    if getattr(b, 'location', None) else None),
            'lng': (getattr(b, 'location', None).lng
                    if getattr(b, 'location', None) else None),
            'faltan': faltan,
        }

    fichas = [_detalle_ficha(par) for par in cubos['revision']]
    publicadas = [_detalle_ficha(par) for par in cubos['publicadas']]
    # Por nombre para que NADA se mueva de sitio al completarse: una
    # confirmacion que salta no se lee.
    fichas.sort(key=lambda f: (f['nombre'] or '').casefold())
    publicadas.sort(key=lambda f: (f['nombre'] or '').casefold())

    # Los pospuestos, con la MISMA medida de categoria: la tercera
    # lista de la misma tarjeta. Solo los que todavia deban algo — el
    # que se completo despues de posponerlo no vuelve a estorbar.
    pospuestos_fichas = [
        _detalle_ficha((b, faltantes_de(b)))
        for b in grupo
        if (b.id in pospuestos and con_trabajo(b)
            and _es_de_categoria(b, categoria))
    ]
    pospuestos_fichas.sort(key=lambda f: (f['nombre'] or '').casefold())

    return Response({
        'municipio': real,
        'provincia': (cab['provincia'] if cab else provincia),
        'cabecera': ({'lat': cab['lat'], 'lng': cab['lng']} if cab else None),
        'radio_km': RADIO_KM,
        # Las fichas del municipio —o de la categoria si hay filtro—,
        # pospuestas incluidas: «fichas» es un hecho, no trabajo.
        'total': (
            len(grupo) if not categoria
            else sum(1 for b in grupo if _es_de_categoria(b, categoria))
        ),
        'con_revision': len(fichas),
        'con_publicadas': len(publicadas),
        # Lo que espera publicarse de ESTE trabajo (sin pospuestos):
        # con filtro, es el «esperando publicarse» del resumen.
        'en_revision': sum(
            1 for b, _ in cubos['revision']
            if b.publication_status.slug != 'publicado'
        ),
        # Para el desplegable de filtro, siempre.
        'categorias': categorias,
        'pospuestos': pospuestos_fichas,
        'campos': ETIQUETAS_PENDIENTES,
        # El desglose cuenta lo que falta en las DOS listas (con el
        # filtro aplicado): es el trabajo del municipio, obligatorios y
        # opcionales.
        'por_campo': contar_pendientes(
            [b for b, _ in cubos['revision'] + cubos['publicadas']],
        ),
        'fichas': fichas,
        'publicadas': publicadas,
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def pospuesto(request):
    """Posponer o retomar una ficha del reporte (DISENO.md seccion 11.1).

    El editor sabe que hay negocios que no desea completar o que no se
    pueden completar: esto los saca de SUS listas de trabajo a la de
    «pospuestos», sin tocar la ficha ni su publicacion. Es una decision
    humana y reversible —«retomar» la devuelve—, y es por DUENO: lo que
    uno pospone no le estorba al otro.

    Mismo candado que el GET (``_acceso_reporte``): el token manda
    sobre la sesion y al colaborador solo le tocan fichas de SU
    municipio (§11-i). Todo lo demas lo recalcula el reporte en su
    proxima lectura, asi que aqui solo se guarda el gesto.
    """
    colaborador, usuario, error = _acceso_reporte(request)
    if error is not None:
        return error

    ficha = str(request.data.get('ficha') or '').strip()
    if not ficha.isdigit():
        return Response(
            {'detail': 'Falta la ficha que quieres posponer.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    biz = Business.objects.filter(id=int(ficha)).select_related(
        'location',
    ).first()
    if biz is None:
        return Response(
            {'detail': 'No existe esa ficha.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    loc = getattr(biz, 'location', None)
    municipio = ((loc.municipality if loc else '') or '').strip()
    municipio = municipio or SIN_MUNICIPIO
    if colaborador is not None and not _le_toca(colaborador, municipio):
        return Response(
            {'detail': 'A este token le toca otro municipio.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    dueno = (
        {'colaborador': colaborador} if colaborador is not None
        else {'usuario': usuario}
    )
    querido = bool(request.data.get('pospuesto'))
    if querido:
        Pospuesto.objects.get_or_create(negocio=biz, **dueno)
    else:
        Pospuesto.objects.filter(negocio=biz, **dueno).delete()

    return Response({'ficha': biz.id, 'pospuesto': querido})
