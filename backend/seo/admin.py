from django.contrib import admin

from .models import SeoRuta, SeoRobots


@admin.register(SeoRuta)
class SeoRutaAdmin(admin.ModelAdmin):
    """Las metas de cada ruta fija, tal como las verá un buscador."""

    list_display = ['ruta', 'titulo', 'noindex']
    search_fields = ['ruta', 'titulo', 'descripcion']


@admin.register(SeoRobots)
class SeoRobotsAdmin(admin.ModelAdmin):
    """La fila única del robots.txt: sin duplicar y sin borrar.

    El contenido es texto plano porque eso es lo que sirve el
    servidor; si la fila no existe, manda el fichero del build.
    """

    list_display = ['__str__', 'actualizado']

    def has_add_permission(self, request):
        # Solo una configuración: no hay segunda fila que añadir.
        return SeoRobots.cargar() is None

    def has_delete_permission(self, request, obj=None):
        # No se borra la configuración; se edita o se deja vacía
        # (vacía = volver al fichero del build).
        return False
