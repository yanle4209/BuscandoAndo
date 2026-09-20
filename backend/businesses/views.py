import math
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from .models import Business
from .serializers import BusinessListSerializer, BusinessDetailSerializer


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

        # Busqueda por texto
        search = params.get('text') or params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search)
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
            tier_order = {'large': 0, 'medium': 1, 'small': 2}
            all_featured = list(qs)
            all_featured.sort(key=lambda b: tier_order.get(b.featured_tier or 'small', 2))
            qs = Business.objects.filter(id__in=[b.id for b in all_featured])

        # Filtrar por radio (haversine en Python)
        lat = params.get('lat')
        lng = params.get('lng')
        radius_km = float(params.get('radius', 10))

        if lat and lng:
            try:
                user_lat = float(lat)
                user_lng = float(lng)

                business_ids = []
                for biz in qs:
                    loc = getattr(biz, 'location', None)
                    if loc:
                        biz_lat = loc.lat if hasattr(loc, 'lat') else getattr(loc, 'latitude', None)
                        biz_lng = loc.lng if hasattr(loc, 'lng') else getattr(loc, 'longitude', None)
                        if biz_lat and biz_lng:
                            dist = haversine_distance(
                                user_lat, user_lng,
                                float(biz_lat), float(biz_lng)
                            )
                            if dist <= radius_km:
                                business_ids.append(biz.id)

                qs = qs.filter(id__in=business_ids)
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'], url_path='featured-by-search')
    def featured_by_search(self, request):
        """Devuelve hasta 3 destacados activos (1 large, 1 medium, 1 small) que coincidan con la busqueda."""
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

        # If no search filters, return empty
        if not search and not category and not city:
            return Response([])

        # Pick 1 large, 1 medium, 1 small
        result = []
        for tier in ['large', 'medium', 'small']:
            biz = qs.filter(featured_tier=tier).first()
            if biz:
                result.append(biz)

        serializer = BusinessListSerializer(result, many=True)
        return Response(serializer.data)
