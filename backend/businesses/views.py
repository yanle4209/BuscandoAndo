from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Case, IntegerField, Q, Value, When
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
from .models import Business, Correction
from .serializers import BusinessListSerializer, BusinessDetailSerializer, CorrectionCreateSerializer, CorrectionSerializer

# Se traen los nombres sueltos y no el modulo: la vista se llama
# ``pendientes`` igual que el modulo, y dentro de la funcion el nombre
# local taparia al importado.
from .pendientes import (
    ETIQUETAS as ETIQUETAS_PENDIENTES,
    contar_pendientes,
    faltantes_de,
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

    dentro = []
    for biz in qs:
        loc = getattr(biz, 'location', None)
        if loc is None:
            continue
        biz_lat = getattr(loc, 'lat', None)
        biz_lng = getattr(loc, 'lng', None)
        if biz_lat is None or biz_lng is None:
            continue
        if haversine_distance(user_lat, user_lng, biz_lat, biz_lng) <= radius_km:
            dentro.append(biz.id)

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


class BusinessViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API publica de negocios.
    Solo muestra negocios PUBLICADOS.
    Soporta busqueda por radio (10km).
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
    """Las cabeceras municipales de todo el pais (158).

    Un dato, dos usos (DISENO.md R3):

    * ancla del circulo de 5 km cuando el usuario no da su ubicacion, y
    * fuente del selector manual de municipio.

    Se devuelve una lista plana agrupable por el cliente: la agrupacion por
    provincia es cosa de la interfaz, no del API.
    """
    return Response(geografia.cabeceras())


def _provincia_de(grupo):
    """La provincia de la primera ficha que la traiga. Texto libre en la
    base, asi que se lee de los datos y no se adivina."""
    for b in grupo:
        loc = getattr(b, 'location', None)
        if loc is not None and loc.province:
            return loc.province
    return ''


def _fila(nombre, grupo, provincia=''):
    """Una fila del listado: el trabajo que hay en un municipio."""
    return {
        'municipio': nombre,
        'provincia': provincia,
        'total': len(grupo),
        'con_pendientes': sum(1 for b in grupo if faltantes_de(b)),
        'en_revision': sum(
            1 for b in grupo if b.publication_status.slug != 'publicado'
        ),
    }


def _le_toca(colaborador, municipio):
    """§11-i: al colaborador le toca SU municipio, y solo el suyo.

    Se compara normalizado porque el nombre de ``Colaborador.municipio``
    lo teclea el admin y el del reporte viene de texto libre: 'Bani' y
    'Baní' son el mismo municipio.
    """
    asignado = (colaborador.municipio or '').strip()
    return bool(asignado) and normalizar(asignado) == normalizar(municipio)


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
        .prefetch_related('hours')
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


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def pendientes(request):
    """Reporte de pendientes por municipio (DISENO.md seccion 11.1).

    La ficha de trabajo del editor. Sin ``?municipio=`` lista **todos los
    municipios del padron** —con cuantas le falta algo y cuantas esperan
    publicacion— para elegir donde trabajar; con el parametro, el detalle
    de ese municipio, agrupado por campo faltante.

    Sale de lo ya decidido y **no guarda nada nuevo**: el municipio lo da
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

    # ---------------------------- quien pregunta ----------------------
    # El TOKEN manda: quien lo trae esta declarando "soy este
    # colaborador", y eso va por delante de la sesion. Sin el, manda la
    # sesion de admin (la lista entera); sin ninguna de las dos, 403.
    #
    # Hace falta porque la sesion vive en el MISMO navegador: con el
    # admin logueado, esta pantalla devolvia los 158 municipios y el
    # navegador se quedaba con el primero (Azua), diciendole a quien
    # tenia el token delante que su municipio era Azua.
    colaborador = colaborador_de(request)

    if colaborador is None and token_de(request):
        # Quien manda un token que no vale (o que esta apagado) no es lo
        # mismo que quien no manda nada: el primero puede arreglarlo.
        return Response(
            {'detail': 'Token de colaborador invalido o inactivo.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    usuario = getattr(request, 'user', None)
    es_admin = bool(
        usuario is not None and usuario.is_authenticated and usuario.is_staff
    )

    if colaborador is None and not es_admin:
        return Response(
            {'detail': 'Sesion de administrador o token de colaborador.'},
            status=status.HTTP_403_FORBIDDEN,
        )

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

    negocios = (
        Business.objects
        .select_related('location', 'contact', 'category', 'publication_status')
        .prefetch_related('hours')
    )

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
            fila = _fila(nombre, grupos_por_norma.get(clave, []), provincia)
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
                )
            )

        # Lo que no casa con ninguna cabecera —incluidas las fichas sin
        # municipio— tampoco se puede perder: no poder asignarlas es
        # justo algo que hay que ver.
        for nombre, grupo in grupos.items():
            if normalizar(nombre) not in claves_del_padron:
                filas.append(_fila(nombre, grupo, _provincia_de(grupo)))

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

    con_faltantes = [
        (b, faltantes_de(b)) for b in grupo
    ]
    fichas = [
        {
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
        for b, faltan in con_faltantes if faltan
    ]
    # Las no publicadas primero: son las que hay que PUBLICAR (accion 2 de
    # §11-j) y solo se diferencian de las demas en un clic. Las publicadas,
    # completar (accion 1).
    fichas.sort(key=lambda f: (f['estado'] == 'publicado',
                               (f['nombre'] or '').casefold()))

    return Response({
        'municipio': real,
        'provincia': (cab['provincia'] if cab else provincia),
        'cabecera': ({'lat': cab['lat'], 'lng': cab['lng']} if cab else None),
        'radio_km': RADIO_KM,
        'total': len(grupo),
        'con_pendientes': len(fichas),
        'campos': ETIQUETAS_PENDIENTES,
        'por_campo': contar_pendientes(grupo),
        'fichas': fichas,
    })
