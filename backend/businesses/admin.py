from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from .models import Business, FEATURED_LIMITS, FEATURED_WEEKS_CHOICES
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.admin import BusinessHoursInline
from business_images.admin import BusinessImageInline


class BusinessLocationInline(admin.StackedInline):
    model = BusinessLocation
    extra = 1
    max_num = 1
    fields = ['street', 'sector', 'municipality', 'district', 'province', 'postal_code', 'country', 'latitude', 'longitude']


class BusinessContactInline(admin.StackedInline):
    model = BusinessContact
    extra = 1
    max_num = 1


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    change_list_template = 'admin/businesses/business/changelist.html'
    change_form_template = 'admin/businesses/business/change_form.html'

    list_display = [
        'name', 'get_category', 'get_publication_status',
        'get_operational_status', 'is_featured', 'featured_tier',
        'get_featured_duration', 'get_city', 'created_at',
    ]
    list_filter = [
        'publication_status',
        'operational_status',
        'category',
        'is_featured',
        'featured_tier',
        'featured_permanent',
        'created_at',
    ]
    search_fields = ['name', 'description', 'short_description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_featured', 'featured_tier']
    list_per_page = 25
    ordering = ['-is_featured', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'get_featured_stats', 'featured_start_date', 'featured_end_date']

    inlines = [
        BusinessLocationInline,
        BusinessContactInline,
        BusinessHoursInline,
        BusinessImageInline,
    ]

    fieldsets = (
        ('Informacion Basica', {
            'fields': ('name', 'slug', 'category', 'description', 'short_description')
        }),
        ('Estados', {
            'fields': ('publication_status', 'operational_status')
        }),
        ('Destacados', {
            'fields': (
                'is_featured', 'featured_tier', 'featured_permanent',
                'featured_weeks', 'featured_start_date', 'featured_end_date',
                'get_featured_stats',
            ),
        }),
    )

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_url'] = reverse('import_json')
        extra_context['export_url'] = reverse('export_json')
        stats = self._get_featured_stats()
        extra_context['featured_stats'] = stats
        return super().changelist_view(request, extra_context=extra_context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        stats = self._get_featured_stats()
        extra_context['featured_stats'] = stats
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """Validate featured limits before saving."""
        if obj.is_featured and obj.featured_tier:
            # Auto-set defaults if not provided
            if not obj.featured_permanent and not obj.featured_weeks:
                obj.featured_permanent = True
            try:
                obj.full_clean()
            except Exception as e:
                messages.error(request, str(e))
                return
        super().save_model(request, obj, form, change)

    def _get_featured_stats(self):
        """Get current featured counts per tier per category."""
        stats = {}
        for tier, label in Business.FEATURED_TIERS:
            count = Business.objects.filter(is_featured=True, featured_tier=tier).count()
            limit = FEATURED_LIMITS[tier]
            stats[tier] = {'count': count, 'limit': limit, 'label': label}
        total = Business.objects.filter(is_featured=True).count()
        stats['total'] = {'count': total, 'limit': 'N/A', 'label': 'Total activos'}
        return stats

    def get_featured_stats(self, obj):
        """Display featured stats in the change form."""
        stats = self._get_featured_stats()
        lines = []
        for tier in ['large', 'medium', 'small']:
            s = stats[tier]
            color = '#22c55e' if s['count'] < s['limit'] else '#ef4444'
            lines.append(
                f'<span style="color:{color};font-weight:bold">'
                f'{s["label"]}: {s["count"]}/{s["limit"]} por categoria</span>'
            )
        total = stats['total']
        lines.append(
            f'<span style="color:#B3B334;font-weight:bold">'
            f'{total["label"]}: {total["count"]}</span>'
        )

        # Show expiration info for current business
        if obj.pk and obj.is_featured:
            lines.append('<br><br>')
            if obj.featured_permanent:
                lines.append(
                    '<span style="color:#B3B334;font-weight:bold">'
                    'Tipo: PERMANENTE</span>'
                )
            elif obj.featured_end_date:
                remaining = obj.featured_days_remaining
                if remaining is not None and remaining > 0:
                    lines.append(
                        f'<span style="color:#22c55e;font-weight:bold">'
                        f'Expira: {obj.featured_end_date.strftime("%d/%m/%Y")} '
                        f'({remaining} dias restantes)</span>'
                    )
                else:
                    lines.append(
                        '<span style="color:#ef4444;font-weight:bold">'
                        'EXPIRADO</span>'
                    )
            if obj.featured_start_date:
                lines.append(
                    f'<br><span style="color:#888">'
                    f'Inicio: {obj.featured_start_date.strftime("%d/%m/%Y %H:%M")}</span>'
                )

        return format_html('<br>'.join(lines))
    get_featured_stats.short_description = 'Estado de Destacados'
    get_featured_stats.allow_tags = True

    def get_featured_duration(self, obj):
        """Show featured duration in list."""
        if not obj.is_featured:
            return '-'
        if obj.featured_permanent:
            return format_html('<span style="color:#B3B334;font-weight:bold">Permanente</span>')
        if obj.featured_end_date:
            remaining = obj.featured_days_remaining
            if remaining is not None and remaining > 0:
                return format_html(
                    '<span style="color:#22c55e">{} dias</span>',
                    remaining
                )
            else:
                return format_html('<span style="color:#ef4444">Expirado</span>')
        return '-'
    get_featured_duration.short_description = 'Duracion'
    get_featured_duration.allow_tags = True

    def get_category(self, obj):
        return obj.category.name if obj.category else '-'
    get_category.short_description = 'Categoria'
    get_category.admin_order_field = 'category__name'

    def get_publication_status(self, obj):
        return obj.publication_status.name if obj.publication_status else '-'
    get_publication_status.short_description = 'Estado Publicacion'
    get_publication_status.admin_order_field = 'publication_status__name'

    def get_operational_status(self, obj):
        return obj.operational_status.name if obj.operational_status else '-'
    get_operational_status.short_description = 'Estado Operativo'
    get_operational_status.admin_order_field = 'operational_status__name'

    def get_city(self, obj):
        location = getattr(obj, 'location', None)
        return location.municipality if location and location.municipality else '-'
    get_city.short_description = 'Municipio'
