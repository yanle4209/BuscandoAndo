"""El panel de las metricas: donde se miran, sin salir del admin.

Dos modelos de solo lectura (los escribe el trafico, no la gente) y
un resumen a 14 dias colgado del propio listado, para que mirar las
cifras cueste un clic y no aprenderse una herramienta nueva.
"""
import datetime

from django.contrib import admin
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from .models import PLATAFORMAS, EVENTOS, TerminoDia, UsoDiario


@admin.register(UsoDiario)
class UsoAdmin(admin.ModelAdmin):
    """Los contadores del dia: solo lectura.

    Se puede borrar (la retencion es cosa del admin: un dia se limpia
    lo viejo), pero ni anadir ni editar: un numero tecleado a mano no
    es dato de nadie.
    """

    list_display = ('fecha', 'evento', 'provincia', 'municipio',
                    'plataforma', 'total')
    list_filter = ('evento', 'plataforma', 'fecha')
    date_hierarchy = 'fecha'
    search_fields = ('municipio', 'provincia')
    ordering = ('-fecha', 'evento')
    change_list_template = 'admin/uso/usodiario/changelist.html'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_urls(self):
        """El resumen cuelga del listado: /admin/uso/usodiario/resumen/."""
        urls = super().get_urls()
        propio = [
            path(
                'resumen/',
                self.admin_site.admin_view(self.resumen_view),
                name='uso_usodiario_resumen',
            ),
        ]
        return propio + urls

    def resumen_view(self, request):
        """Una sola pantalla con los ultimos 14 dias.

        Cuatro tablas y nada mas: totales por evento y dia (la grafica
        sin grafica), por plataforma, los municipios que mas pesan, y
        —la que sirve para decidir— lo que se busca y no se encuentra.
        """
        hoy = timezone.localdate()
        desde = hoy - datetime.timedelta(days=13)
        dias = [desde + datetime.timedelta(days=paso) for paso in range(14)]

        filas = (UsoDiario.objects.filter(fecha__gte=desde)
                 .values('fecha', 'evento')
                 .annotate(n=Sum('total')))

        def clave(valor):
            """La fecha como llave de tabla, venga como venga.

            El ``values('fecha')`` devuelve la fecha como objeto
            ``date``... o como ``datetime``, o hasta como texto, segun
            el motor y la version del conector. Si la llave del
            diccionario no coincide EXACTAMENTE en tipo con la de la
            lista de dias, el ``.get(dia, 0)`` falla en silencio y la
            tabla sale entera en ceros — que es lo que le paso al
            panel la primera vez en produccion. Formateada como
            'AAAA-MM-DD' todas las formas caen en la misma llave.
            """
            if hasattr(valor, 'strftime'):
                return valor.strftime('%Y-%m-%d')
            return str(valor)

        por_evento = {}
        for fila in filas:
            por_evento.setdefault(fila['evento'], {})[
                clave(fila['fecha'])] = fila['n']

        filas_tabla = []
        for codigo, etiqueta in EVENTOS:
            if codigo not in por_evento:
                continue
            celdas = [por_evento[codigo].get(clave(dia), 0) for dia in dias]
            filas_tabla.append({
                'etiqueta': etiqueta,
                'celdas': celdas,
                'total': sum(celdas),
            })

        plataformas = (UsoDiario.objects.filter(fecha__gte=desde)
                       .values('plataforma')
                       .annotate(n=Sum('total'))
                       .order_by('-n'))
        nombres = dict(PLATAFORMAS)
        for fila in plataformas:
            fila['etiqueta'] = nombres.get(fila['plataforma'],
                                            fila['plataforma'])

        lugares = (UsoDiario.objects.filter(fecha__gte=desde)
                   .exclude(municipio='')
                   .values('provincia', 'municipio')
                   .annotate(n=Sum('total'))
                   .order_by('-n')[:10])

        context = {
            **self.admin_site.each_context(request),
            'title': 'Uso: ultimos 14 dias',
            'opts': self.model._meta,
            'desde': desde,
            'hoy': hoy,
            'dias': dias,
            'filas_tabla': filas_tabla,
            'totales_dia': [
                sum(fila['celdas'][i] for fila in filas_tabla)
                for i in range(14)
            ],
            'total_general': sum(fila['total'] for fila in filas_tabla),
            'plataformas': plataformas,
            'lugares': lugares,
            'terminos': list(
                TerminoDia.objects.filter(fecha__gte=desde)
                .order_by('-busquedas')[:10]),
            'huecos': list(
                TerminoDia.objects.filter(fecha__gte=desde,
                                          sin_resultados__gt=0)
                .order_by('-sin_resultados')[:10]),
        }
        return TemplateResponse(request, 'uso/resumen.html', context)


@admin.register(TerminoDia)
class TerminoAdmin(admin.ModelAdmin):
    """Lo que se teclea en el buscador: igual de solo lectura."""

    list_display = ('fecha', 'termino', 'busquedas', 'sin_resultados')
    list_filter = ('fecha',)
    search_fields = ('termino',)
    ordering = ('-fecha', '-busquedas')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
