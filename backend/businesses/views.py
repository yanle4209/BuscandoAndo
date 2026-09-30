import csv
import math
from functools import lru_cache

from django.conf import settings
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone
from .models import Business, Correction
from .serializers import BusinessListSerializer, BusinessDetailSerializer, CorrectionCreateSerializer, CorrectionSerializer

# Radio de busqueda en km. R1: las busquedas son unica y exclusivamente a
# 5 km del punto activo (la ubicacion del usuario; la cabecera municipal,
# si no la hay). Lo impone el backend: el cliente puede pedir menos, nunca
# mas. Ver DISENO.md R1.3.
RADIO_KM = 5.0

# Fuente estatica de las 158 cabeceras municipales (DISENO.md seccion 9).
CABECERAS_CSV = settings.BASE_DIR / 'data' / 'cabeceras_municipales.csv'


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

        # Busqueda por texto. Mismos campos que featured_by_search: si los
        # destacados buscan en la categoria y el listado no, "restaurante"
        # enseña 2 destacados sobre "0 resultados" (lo contrario de que
        # siempre haya resultados si estan disponibles).
        search = params.get('text') or params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search) |
                Q(category__name__icontains=search)
            )

        # Filtrar por categoria
        category = params.get('category')
        if category:
            try:
                qs = qs.filter(category__id=int(category))
            except (ValueError, TypeError):
                qs = qs.filter(category__slug=category)

        # Filtrar por ciudad (municipality)
        city = params.get('city')
        if city:
            qs = qs.filter(location__municipality__icontains=city)

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
        city = params.get('city')

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

        # Filter by search text if provided
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search) |
                Q(category__name__icontains=search)
            )

        # Filter by category if provided
        if category:
            try:
                qs = qs.filter(category__id=int(category))
            except (ValueError, TypeError):
                qs = qs.filter(category__slug=category)

        # Filter by city if provided
        if city:
            qs = qs.filter(location__municipality__icontains=city)

        # R1.2: los destacados del buscador entran en el MISMO filtro de 5 km
        # que los resultados normales. Sin coordenadas no se recorta (y sin
        # busqueda no hay fila que devolver, que es la regla de abajo).
        lat = params.get('lat')
        lng = params.get('lng')
        if lat and lng:
            qs = negocios_en_radio(qs, lat, lng, parse_radio(params.get('radius')))

        # If no search filters, return empty
        if not search and not category and not city:
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


@lru_cache(maxsize=1)
def _cabeceras():
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


@api_view(['GET'])
def cabeceras(request):
    """Las cabeceras municipales de todo el pais (158).

    Un dato, dos usos (DISENO.md R3):

    * ancla del circulo de 5 km cuando el usuario no da su ubicacion, y
    * fuente del selector manual de municipio.

    Se devuelve una lista plana agrupable por el cliente: la agrupacion por
    provincia es cosa de la interfaz, no del API.
    """
    return Response(_cabeceras())
