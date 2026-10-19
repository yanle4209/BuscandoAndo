"""Las metricas de uso: que se busca, que se abre, que se corrige.

Lo importante de aqui es lo que NO hay: no hay cookies, ni scripts de
terceros, ni identidades, ni IPs. Cada peticion que el backend ya
atiende suma UNA vez a un contador del dia, y de esa suma solo salen
cuatro cosas — fecha, evento, lugar y plataforma — mas el termino que
el usuario tecleo en el buscador, guardado normalizado y sin ninguna
referencia a quien lo escribio.

Se cuenta DENTRO de la vista que ya atiende la peticion, no con
llamadas extra del cliente: menos codigo, imposible de descontar dos
veces y nada que instalar en las apps viejas. Y si la base falla, la
metrica se pierde con un aviso en el log y la busqueda sigue su
camino: un contador jamas tumba una peticion (hay test de eso).

La plataforma la declara el propio cliente en ``X-Plataforma`` (el
axios de la web y el cliente de la app); sin esa cabecera se miran
senales huras del User-Agent, y lo que no se parece a nada queda como
lo que es: ``otro``.
"""
import logging

from django.db import IntegrityError, models
from django.db.models import F
from django.utils import timezone

from businesses import geografia

logger = logging.getLogger(__name__)

# Los eventos que se cuentan. Los dos ultimos los dispara la fase
# geografica (banner de fuera de zona y lista de espera): se declaran
# ya para no tener que migrar cuando entren.
EVENTOS = [
    ('consulta', 'Consulta al listado'),
    ('ficha', 'Ficha abierta'),
    ('correccion', 'Correccion enviada'),
    ('fuera_zona', 'Intento fuera de la fase'),
    ('aviso_interes', 'Aviso de lista de espera'),
]

PLATAFORMAS = [
    ('web', 'Web'),
    ('app', 'App'),
    ('otro', 'Otra'),
]

# A que distancia de una cabecera se le asigna el lugar al punto de la
# consulta. Generosa a proposito: el punto casi nunca cae en el centro
# exacto del pueblo, y a 15 km el vecindario sigue siendo suyo. Mas
# alla no hay municipio al que echar la culpa: el lugar queda vacio.
RADIO_LUGAR_KM = 15.0

# El termino tecleado, normalizado, no mas largo que esto: un buscador
# de pueblo no es un chat.
TERMINO_MAX = 80


class UsoDiario(models.Model):
    """Contador agregado: dia x evento x lugar x plataforma.

    La fila NACE al primer evento del dia y solo sube: nunca baja ni
    se edita a mano (el admin la deja solo lectura). Asi la tabla
    crece con lo que crece el calendario, no con el trafico.
    """

    fecha = models.DateField(verbose_name='Dia')
    evento = models.CharField(
        max_length=20, choices=EVENTOS, verbose_name='Evento')
    provincia = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Provincia')
    municipio = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Municipio')
    plataforma = models.CharField(
        max_length=10, choices=PLATAFORMAS, default='otro',
        verbose_name='Plataforma')
    total = models.PositiveIntegerField(default=0, verbose_name='Veces')

    class Meta:
        verbose_name = 'Contador de uso'
        verbose_name_plural = 'Contadores de uso'
        ordering = ['-fecha', 'evento']
        constraints = [
            models.UniqueConstraint(
                fields=['fecha', 'evento', 'provincia', 'municipio',
                        'plataforma'],
                name='uso_diario_un_dia_un_contador',
            ),
        ]

    def __str__(self):
        lugar = ' · '.join(x for x in (self.municipio, self.provincia) if x)
        return '%s · %s · %d (%s / %s)' % (
            self.fecha, self.get_evento_display(), self.total,
            lugar or 'sin lugar', self.get_plataforma_display())


class TerminoDia(models.Model):
    """Que se teclea en el buscador y si se encuentra: dia x termino.

    El termino se guarda normalizado — minusculas y sin tildes, la
    MISMA clave con que puntua el buscador — para que "Moca", "moca"
    y "móca" cuenten juntos. Los dos contadores de una vez: cuantas
    veces se busco y cuantas termino en cero resultados, que es
    exactamente la lista de lo que falta levantar.
    """

    fecha = models.DateField(verbose_name='Dia')
    termino = models.CharField(max_length=TERMINO_MAX, verbose_name='Termino')
    busquedas = models.PositiveIntegerField(default=0, verbose_name='Busquedas')
    sin_resultados = models.PositiveIntegerField(
        default=0, verbose_name='Sin resultados')

    class Meta:
        verbose_name = 'Termino buscado'
        verbose_name_plural = 'Terminos buscados'
        ordering = ['-fecha', '-busquedas']
        constraints = [
            models.UniqueConstraint(
                fields=['fecha', 'termino'],
                name='uso_termino_un_dia_un_termino',
            ),
        ]

    def __str__(self):
        return '%s · %s (%d, %d sin)' % (
            self.fecha, self.termino, self.busquedas, self.sin_resultados)


def plataforma_de(request):
    """``web``, ``app`` u ``otro``, sin preguntarle nada al usuario.

    Manda la cabecera ``X-Plataforma`` cuando la trae (la pone el
    cliente de la casa); sin ella, senales huras del User-Agent. El
    resultado puede ser torpe en los bordes — un navegador viejo sin
    Mozilla es ``otro`` — pero nunca es mentira: no se deduce de nada
    que el usuario controle ni de nada que lo identifique.
    """
    try:
        cabeceras = request.headers
    except AttributeError:
        cabeceras = {}
    declarada = (cabeceras.get('X-Plataforma') or '').strip().lower()
    if declarada in ('web', 'app'):
        return declarada
    ua = (cabeceras.get('User-Agent') or '').strip().lower()
    if ua.startswith('okhttp') or ua.startswith('ktor') or 'dalvik' in ua:
        return 'app'
    if 'mozilla' in ua:
        return 'web'
    return 'otro'


def lugar_de(request):
    """``(provincia, municipio)`` del punto de la peticion, o ``('', '')``.

    El punto viaja como ``lat``/``lng`` en la query (R1). Se le asigna
    la cabecera mas cercana dentro de ``RADIO_LUGAR_KM``: el punto
    elegido a mano es la cabecera misma, y el GPS del vecino esta a un
    par de calles. Sin coordenadas no hay lugar que declarar.
    """
    params = getattr(request, 'query_params', None)
    if params is None:
        params = getattr(request, 'GET', {})
    try:
        lat = float(params.get('lat'))
        lng = float(params.get('lng'))
    except (TypeError, ValueError):
        return '', ''
    cab = geografia.cabecera_mas_cercana(lat, lng, RADIO_LUGAR_KM)
    if not cab:
        return '', ''
    return cab['provincia'], cab['municipio']


def _subir(modelo, buscar, incrementar):
    """``+1`` atomico a cada campo de ``incrementar`` del registro que
    combine con ``buscar``; si no existe, lo crea con esos campos a 1.

    Dos pasadas y un desempate de carreras: primero un UPDATE con
    ``F()``, que no crea filas; si no toco ninguna, un CREATE; si en
    el medio otra peticion gano la partida (IntegrityError), se
    repite el UPDATE, que ahi ya encuentra la fila.

    Las claves de ``incrementar`` son los campos que suben; sus
    valores son lo que se crea si la fila no existe (1). Ojo: al
    armar el ``F()`` va el NOMBRE del campo — ``F('total')`` — y no
    su valor: ``F(1)`` Django lo lee como una referencia al campo
    "1" y revienta al resolverlo.
    """
    cambios = {campo: F(campo) + 1 for campo in incrementar}
    if modelo.objects.filter(**buscar).update(**cambios):
        return
    try:
        modelo.objects.create(**buscar, **incrementar)
    except IntegrityError:
        modelo.objects.filter(**buscar).update(**cambios)


def registrar(evento, request, *, termino=None, resultados=None,
              provincia=None, municipio=None):
    """Suma UNA vez el evento al contador del dia. **Nunca lanza.**

    Si algo falla aqui (la base no puede escribir, el dato no cierra),
    lo unico que pasa es que la metrica se pierde y el log avisa: la
    peticion que la trajo sigue su camino. Un contador jamas tumba una
    busqueda — hay test de eso.

    ``termino`` solo lo manda el listado cuando el usuario tecleo
    algo; ``resultados`` es cuantas filas devolvio, y con 0 se sube
    tambien el contador de ``sin_resultados``. El lugar sale del punto
    de la query salvo que se pase a mano.
    """
    try:
        hoy = timezone.localdate()
        if provincia is None and municipio is None:
            provincia, municipio = lugar_de(request)
        _subir(
            UsoDiario,
            {
                'fecha': hoy,
                'evento': evento,
                'provincia': provincia or '',
                'municipio': municipio or '',
                'plataforma': plataforma_de(request),
            },
            {'total': 1},
        )
        if termino:
            clave = geografia.normalizar(termino)[:TERMINO_MAX]
            if clave:
                incrementar = {'busquedas': 1}
                if resultados == 0:
                    incrementar['sin_resultados'] = 1
                _subir(TerminoDia, {'fecha': hoy, 'termino': clave},
                       incrementar)
    except Exception:
        logger.exception('No se pudo contar el evento %r', evento)
