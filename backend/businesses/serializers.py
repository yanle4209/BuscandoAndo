from rest_framework import serializers
from .models import Business
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from business_images.models import BusinessImage
from datetime import date, time as dt_time


STATUS_NAMES = {
    'abierto': 'Abierto',
    'cerrado': 'Cerrado',
    'por-horario': 'Por Horario',
}


def compute_operational_status(business):
    """
    Calcula el estado operativo real basado en horarios y feriados.
    Retorna: 'abierto', 'cerrado', 'por-horario'
    """
    today = date.today()
    day_index = today.weekday()  # 0=Lunes
    day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    today_name = day_names[day_index]

    hours = business.hours.filter(day=today_name).first()
    if not hours:
        return business.operational_status.slug if business.operational_status else 'cerrado'

    # Si es día de fiesta, cerrado
    if hours.is_holiday:
        return 'cerrado'

    # Si está marcado como cerrado
    if hours.is_closed:
        return 'cerrado'

    # Si no tiene horarios definidos
    if not hours.open_time or not hours.close_time:
        return 'cerrado'

    # Verificar horario actual
    import datetime as _dt
    now = _dt.datetime.now().time()

    if hours.open_time <= now < hours.close_time:
        return 'abierto'
    else:
        return 'por-horario'


def get_effective_status_name(business):
    slug = compute_operational_status(business)
    return STATUS_NAMES.get(slug, 'Sin estado')


class BusinessImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = BusinessImage
        fields = ['id', 'image', 'image_url', 'caption', 'order']

    def get_image_url(self, obj):
        url = str(obj.image)
        if url.startswith('http'):
            return url
        return obj.image.url if obj.image else None


class BusinessLocationSerializer(serializers.ModelSerializer):
    lat = serializers.ReadOnlyField()
    lng = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()

    class Meta:
        model = BusinessLocation
        fields = [
            'street', 'sector', 'municipality', 'district', 'province',
            'postal_code', 'country', 'lat', 'lng', 'full_address',
        ]


class BusinessContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessContact
        fields = ['contact_person', 'phone', 'whatsapp', 'email', 'website']


class BusinessHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHours
        fields = ['day', 'open_time', 'close_time', 'is_closed', 'is_holiday']


class BusinessListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    operational_status_name = serializers.CharField(
        source='operational_status.name', read_only=True
    )
    operational_status_slug = serializers.CharField(
        source='operational_status.slug', read_only=True
    )
    operational_status_color = serializers.CharField(
        source='operational_status.color', read_only=True
    )
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    street = serializers.SerializerMethodField()
    municipality = serializers.SerializerMethodField()
    province = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    whatsapp = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    effective_status = serializers.SerializerMethodField()
    effective_status_name = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            'id', 'name', 'slug', 'short_description',
            'category', 'category_name', 'category_icon',
            'operational_status_name', 'operational_status_slug', 'operational_status_color',
            'effective_status', 'effective_status_name',
            'is_featured', 'featured_tier',
            'latitude', 'longitude',
            'street', 'municipality', 'province',
            'phone', 'whatsapp', 'email',
            'images',
            'created_at',
        ]

    def get_latitude(self, obj):
        loc = getattr(obj, 'location', None)
        return float(loc.latitude) if loc and loc.latitude else None

    def get_longitude(self, obj):
        loc = getattr(obj, 'location', None)
        return float(loc.longitude) if loc and loc.longitude else None

    def get_street(self, obj):
        loc = getattr(obj, 'location', None)
        return loc.street if loc else None

    def get_municipality(self, obj):
        loc = getattr(obj, 'location', None)
        return loc.municipality if loc else None

    def get_province(self, obj):
        loc = getattr(obj, 'location', None)
        return loc.province if loc else None

    def get_phone(self, obj):
        contact = getattr(obj, 'contact', None)
        return contact.phone if contact else None

    def get_whatsapp(self, obj):
        contact = getattr(obj, 'contact', None)
        return contact.whatsapp if contact else None

    def get_email(self, obj):
        contact = getattr(obj, 'contact', None)
        return contact.email if contact else None

    def get_images(self, obj):
        imgs = obj.images.all()[:5]
        return BusinessImageSerializer(imgs, many=True).data

    def get_effective_status(self, obj):
        return compute_operational_status(obj)

    def get_effective_status_name(self, obj):
        return get_effective_status_name(obj)


class BusinessDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    publication_status_name = serializers.CharField(
        source='publication_status.name', read_only=True
    )
    operational_status_name = serializers.CharField(
        source='operational_status.name', read_only=True
    )
    operational_status_color = serializers.CharField(
        source='operational_status.color', read_only=True
    )
    location = BusinessLocationSerializer(read_only=True)
    contact = BusinessContactSerializer(read_only=True)
    hours = BusinessHoursSerializer(many=True, read_only=True)
    images = BusinessImageSerializer(many=True, read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    effective_status = serializers.SerializerMethodField()
    effective_status_name = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            'id', 'name', 'slug', 'description', 'short_description',
            'category', 'category_name', 'category_icon',
            'publication_status', 'publication_status_name',
            'operational_status', 'operational_status_name', 'operational_status_color',
            'effective_status', 'effective_status_name',
            'is_featured', 'featured_tier',
            'latitude', 'longitude',
            'location', 'contact', 'hours', 'images',
            'created_at', 'updated_at',
        ]

    def get_latitude(self, obj):
        loc = getattr(obj, 'location', None)
        return float(loc.latitude) if loc and loc.latitude else None

    def get_longitude(self, obj):
        loc = getattr(obj, 'location', None)
        return float(loc.longitude) if loc and loc.longitude else None

    def get_effective_status(self, obj):
        return compute_operational_status(obj)

    def get_effective_status_name(self, obj):
        return get_effective_status_name(obj)
