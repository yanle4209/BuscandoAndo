"""Contadores del panel (DISENO 15): los numeros de las 4 secciones.

Un tag, una consulta por numero: el indice del admin se pinta una vez
por visita y aqui no hay nada en bucle. Si una cuenta fallase, el panel
NO debe caer — el admin es la puerta de casa —, asi que cada numero se
protege y devuelve 0.
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
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

    def negocios_total():
        return Business.objects.count()

    def en_revision():
        return Business.objects.filter(
            publication_status__slug='en-revision').count()

    contadores = {
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
        'negocios_total': _cuenta(negocios_total),
        'en_revision': _cuenta(en_revision),
    }
    # Lo que pide atencion, sumando las dos bandejas: un solo numero
    # grande en el KPI del dashboard.
    contadores['pendientes_total'] = (
        contadores['reportes_pendientes'] + contadores['envios_pendientes'])
    return contadores


@register.filter
def ba_num(valor):
    """16287 -> 16.287 (separador de miles español, sin humanize)."""
    try:
        return f'{int(valor):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return valor


@register.simple_tag
def panel_provincias(limite=8):
    """Top de provincias por fichas: la grafica horizontal del dashboard.

    Dict con `puntos` (nombre, total y pct respecto al maximo), el
    maximo, el total de fichas con ubicacion y cuantas provincias quedan
    fuera del recorte. Si algo falla, lista vacia: el panel no cae.
    """
    try:
        from business_locations.models import BusinessLocation
        filas = list(
            BusinessLocation.objects
            .filter(province__isnull=False).exclude(province='')
            .values('province').annotate(n=Count('id')).order_by('-n'))
    except Exception:
        filas = []

    maximo = filas[0]['n'] if filas else 0
    top = filas[:limite]
    puntos = [{
        'nombre': f['province'],
        'total': f['n'],
        'pct': max(2, round(f['n'] * 100 / maximo)) if maximo else 0,
    } for f in top]
    return {
        'puntos': puntos,
        'max': maximo,
        'total': sum(f['n'] for f in filas),
        'resto_n': max(0, len(filas) - limite),
    }


@register.simple_tag
def panel_en_revision(limite=6):
    """Las ultimas fichas En Revision, para la tabla del dashboard."""
    try:
        filas = (Business.objects
                 .filter(publication_status__slug='en-revision')
                 .select_related('category')
                 .order_by('-created_at')[:limite])
        return [{
            'pk': b.pk,
            'nombre': b.name,
            'categoria': b.category.name if b.category_id else '—',
            'creada': b.created_at,
        } for b in filas]
    except Exception:
        return []
