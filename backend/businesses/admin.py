from django.contrib import admin
from django import forms
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from . import geografia
from .models import (
    Business, Correction, Colaborador, Envio,
    FEATURED_LIMITS, FEATURED_WEEKS_CHOICES,
)
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
    fields = ['contact_person', 'phone', 'whatsapp', 'email', 'website']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 3})},
    }


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    """Bandeja de avisos de datos incorrectos enviados desde el frontend."""

    list_display = ['business', 'campo', 'estado', 'created_at', 'aviso']
    list_filter = ['estado', 'campo', 'created_at']
    search_fields = ['business__name', 'mensaje', 'nota_admin']
    # El aviso es lo que dijo el visitante: no se edita, se RESUELVE
    # cambiando el estado y dejando una nota interna.
    readonly_fields = ['business', 'campo', 'mensaje', 'created_at']
    list_editable = ['estado']
    actions = [
        'marcar_como_revisada',
        'marcar_como_aplicada',
        'marcar_como_descartada',
    ]

    def aviso(self, obj):
        return f'{obj.mensaje[:60]}…' if len(obj.mensaje) > 60 else obj.mensaje
    aviso.short_description = 'Aviso'

    def _cambiar_estado(self, request, queryset, estado):
        """Solo staff llega aqui (el admin ya lo garantiza)."""
        total = queryset.count()
        queryset.update(
            estado=estado,
            # resolved_at solo tiene sentido cuando el caso cierra.
            resolved_at=timezone.now() if estado in ('aplicada', 'descartada') else None,
        )
        self.message_user(
            request,
            f'{total} correccion(es) marcada(s) como "{estado}".',
            messages.SUCCESS,
        )

    def marcar_como_revisada(self, request, queryset):
        self._cambiar_estado(request, queryset, 'revisada')
    marcar_como_revisada.short_description = 'Marcar seleccionadas como revisadas'

    def marcar_como_aplicada(self, request, queryset):
        self._cambiar_estado(request, queryset, 'aplicada')
    marcar_como_aplicada.short_description = 'Marcar seleccionadas como aplicadas'

    def marcar_como_descartada(self, request, queryset):
        self._cambiar_estado(request, queryset, 'descartada')
    marcar_como_descartada.short_description = 'Marcar seleccionadas como descartadas'


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    change_list_template = 'admin/businesses/business/changelist.html'
    change_form_template = 'admin/businesses/business/change_form.html'

    list_display = [
        'name', 'get_category', 'publication_status',
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
    list_editable = ['publication_status', 'is_featured', 'featured_tier']
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
            'fields': ('name', 'category', 'description', 'short_description')
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

    def save_related(self, request, form, formsets, change):
        """Auto-detect holidays when saving hours."""
        super().save_related(request, form, formsets, change)

        from business_hours.holidays import is_holiday
        from datetime import date

        today = date.today()
        today_idx = today.weekday()  # 0=Lunes
        day_name_to_idx = {'Lunes': 0, 'Martes': 1, 'Miércoles': 2,
                           'Jueves': 3, 'Viernes': 4, 'Sábado': 5, 'Domingo': 6}

        for formset in formsets:
            if formset.model.__name__ == 'BusinessHours':
                for f in formset.forms:
                    day_name = f.cleaned_data.get('day')
                    if not day_name:
                        continue
                    day_idx = day_name_to_idx.get(day_name)
                    if day_idx is None:
                        continue
                    # Calcular fecha de ese día en la semana actual
                    diff = day_idx - today_idx
                    target_date = date.fromordinal(today.toordinal() + diff)
                    holiday_name = is_holiday(target_date)
                    if holiday_name:
                        instance = f.save(commit=False)
                        if not instance.is_holiday:
                            instance.is_holiday = True
                            instance.save()
                            messages.info(
                                request,
                                f'🎉 {day_name} ({holiday_name}) marcado como Dia de Fiesta automaticamente.'
                            )

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
        for tier in ['1', '2', '3', '4']:
            if tier in stats:
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


class ColaboradorForm(forms.ModelForm):
    """El municipio como desplegable del padron, no como texto libre.

    Ya no es solo informativo: es **el único reporte que este token puede
    leer** (§11-i). Un ``'moca '`` con espacios, o un nombre que no
    exista, no daria error en ninguna parte: le cerraria la puerta al
    propio colaborador y nadie se enteraria.
    """

    class Meta:
        model = Colaborador
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        padron = {c['municipio']: c['provincia']
                  for c in geografia.cabeceras()}
        opciones = [('', '— sin municipio —')]
        # Un valor ya guardado y fuera del padron se muestra tal cual: si
        # no, el desplegable lo dejaria sin seleccionar y al guardar se
        # borraria sin que nadie lo notara.
        actual = (self.instance.municipio or '').strip()
        if actual and actual not in padron:
            opciones.append(
                (actual, '%s (fuera del padron)' % actual)
            )
        opciones += [
            (municipio, '%s (%s)' % (municipio, provincia))
            for municipio, provincia in sorted(
                padron.items(), key=lambda par: (par[1], par[0])
            )
        ]
        self.fields['municipio'].widget = forms.Select(choices=opciones)
        self.fields['municipio'].help_text = (
            'El unico municipio que este token puede leer en el reporte de '
            'pendientes. Los envios no se limitan por aqui: el municipio de '
            'cada envio lo declara el propio envio.'
        )


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    """Alta de colaboradores y el token con que firman (DISENO.md 11.5).

    No hay "usuarios" del canal: hay personas que firman. Crear uno aqui
    es entregarle el token; apagarlo (`activo`) lo bloquea a el y solo a
    el, sin tocar a los demas — que es justo la propiedad que hizo que se
    eligiera el token de firma en vez de una cuenta.
    """

    form = ColaboradorForm
    list_display = ['nombre', 'token_corto', 'municipio', 'activo',
                    'ultimo_envio', 'creado_el']
    list_filter = ['activo', 'municipio']
    search_fields = ['nombre', 'municipio']
    # El token se genera en `save()` y no se teclea: se muestra aqui para
    # poder copiarlo y entregarselo, pero no se puede escribir.
    readonly_fields = ['token', 'creado_el', 'ultimo_envio']
    actions = ['bloquear', 'desbloquear']
    fieldsets = [
        (None, {
            'fields': ['nombre', 'municipio', 'activo'],
            'description': (
                'Colaborador NO es usuario: no entra al admin ni a las '
                'fichas. Lee UNA cosa con su token —el reporte de su '
                'municipio— y firma los envios. Eso es lo que permite '
                'bloquear a este sin cerrarle el canal a los demas.'
            ),
        }),
        ('Firma', {
            'fields': ['token'],
            'description': (
                'Se entrega tal cual. La herramienta de levantamiento lo '
                'pide una vez y lo guarda en el navegador. Va en la '
                'cabecera <code>X-Colaborador-Token</code>, nunca en la URL.'
            ),
        }),
        ('Actividad', {
            'fields': ['ultimo_envio', 'creado_el'],
        }),
    ]

    def token_corto(self, obj):
        return (obj.token[:10] + '…') if obj.token else '-'
    token_corto.short_description = 'Token'
    token_corto.admin_order_field = 'token'

    def bloquear(self, request, queryset):
        """§11.5: bloquear a UN colaborador sin cerrar a los demas."""
        actualizados = queryset.update(activo=False)
        self.message_user(
            request,
            '%d colaborador(es) bloqueado(s). Sus envios dejaron de aceptarse.'
            % actualizados,
        )
    bloquear.short_description = 'Bloquear los seleccionados'

    def desbloquear(self, request, queryset):
        actualizados = queryset.update(activo=True)
        self.message_user(
            request, '%d colaborador(es) reactivo(s).' % actualizados,
        )
    desbloquear.short_description = 'Reactivar los seleccionados'


@admin.register(Envio)
class EnvioAdmin(admin.ModelAdmin):
    """Bandeja de auditoria del canal: que decidio el sistema y por que.

    **Solo lectura.** Ahi dentro esta la decision (§11.5) y el cuerpo
    literal de lo que llego: cambiarlo seria reescribir la prueba. Lo que
    se arregla es en la ficha, no aqui.
    """

    list_display = ['recibido_el', 'colaborador', 'estado', 'negocio',
                    'motivos_cortos', 'ip']
    list_filter = ['estado', 'colaborador', 'recibido_el']
    search_fields = ['colaborador__nombre', 'negocio__name', 'datos']
    date_hierarchy = 'recibido_el'

    def has_add_permission(self, request):
        # Los envios los hace el sistema, no la persona.
        return False

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in Envio._meta.fields]

    def motivos_cortos(self, obj):
        if obj.estado == 'rechazado' and obj.motivos:
            return ' | '.join(obj.motivos)
        if obj.faltan:
            return 'Faltan: ' + ', '.join(obj.faltan)
        return '-'
    motivos_cortos.short_description = 'Motivos / faltantes'
