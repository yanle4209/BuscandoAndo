"""Contadores del panel (DISENO 15): los numeros de las 4 secciones.

Un tag, una consulta por numero: el indice del admin se pinta una vez
por visita y aqui no hay nada en bucle. Si una cuenta fallase, el panel
NO debe caer — el admin es la puerta de casa —, asi que cada numero se
protege y devuelve 0.
"""
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.template import Library
from django.utils import timezone

from businesses import geografia
from businesses.models import Business, Colaborador, Correction, Envio
from categories.models import Category
from uso.models import TerminoDia, UsoDiario

register = Library()


def _cuenta(funcion):
    """El numero que devuelva la funcion, o 0 si algo falla."""
    try:
        return funcion() or 0
    except Exception:
        return 0


@register.simple_tag
def panel_contadores():
    """Dict con los contadores de las cuatro secciones del indice."""
    hoy = timezone.localdate()

    def reportes_pendientes():
        return Correction.objects.filter(estado='pendiente').count()

    def envios_pendientes():
        return Envio.objects.filter(estado='pendiente').count()

    def usuarios():
        return get_user_model().objects.count()

    def grupos():
        from django.contrib.auth.models import Group
        return Group.objects.count()

    def colaboradores():
        return Colaborador.objects.count()

    def negocios_publicados():
        return Business.objects.filter(
            publication_status__slug='publicado').count()

    def sitemap_fichas():
        # Mismo filtro que sitemap_xml (DISENO 14): lo que esta en fase
        # y publicado es lo que se anuncia; el resto abre por enlace
        # directo pero con noindex.
        return Business.objects.filter(
            geografia.q_fase(),
            publication_status__slug='publicado').count()

    def metas_rutas():
        from seo.models import SeoRuta
        return SeoRuta.objects.count()

    def categorias():
        return Category.objects.count()

    def uso_hoy():
        return UsoDiario.objects.filter(fecha=hoy).aggregate(
            s=Sum('total'))['s']

    def busquedas_hoy():
        return TerminoDia.objects.filter(fecha=hoy).aggregate(
            s=Sum('busquedas'))['s']

    return {
        'reportes_pendientes': _cuenta(reportes_pendientes),
        'envios_pendientes': _cuenta(envios_pendientes),
        'usuarios': _cuenta(usuarios),
        'grupos': _cuenta(grupos),
        'colaboradores': _cuenta(colaboradores),
        'negocios_publicados': _cuenta(negocios_publicados),
        'sitemap_fichas': _cuenta(sitemap_fichas),
        'metas_rutas': _cuenta(metas_rutas),
        'categorias': _cuenta(categorias),
        'uso_hoy': _cuenta(uso_hoy),
        'busquedas_hoy': _cuenta(busquedas_hoy),
    }
