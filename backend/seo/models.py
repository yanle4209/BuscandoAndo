"""La configuracion de SEO editable a mano (DISENO 15).

El sitio es dinamico: hoy hacen falta dos rutas, mañana otra. Aqui la
meta deja de estar escrita en el codigo y pasa a ser una fila que se
edita desde el panel — sin tocar codigo y sin desplegar.

Lo que NO esta aqui es lo que se deriva de los datos: las metas de
cada ficha salen del propio negocio (se editan en Gestion) y el
sitemap se genera de lo publicado y en fase. Aqui solo lo fijo del
sitio: portada, herramientas y lo que venga.
"""
from django.db import models


class SeoRuta(models.Model):
    """Las metas de una ruta fija, con su clave sin barra.

    La clave es el ``rel`` que ya usa el servidor: '' (portada),
    'levantamiento' y cualquier ruta SPA que se anyada en el futuro.
    Anyadir una fila nueva basta para dar metas a una ruta nueva.
    """

    ruta = models.CharField(
        max_length=100, unique=True, blank=True, verbose_name='Clave de ruta',
        help_text="Ruta SIN barra inicial: vacío para la portada, "
                  "'levantamiento' para esa página, etc.",
    )
    titulo = models.CharField(max_length=200, verbose_name='Titulo')
    descripcion = models.TextField(
        verbose_name='Descripcion',
        help_text='Lo que se ve en Google y al compartir (unos 160 '
                  'caracteres).',
    )
    imagen = models.URLField(
        blank=True, default='', verbose_name='Imagen (URL)',
        help_text='Vacia = la og.png del sitio. Tambien admite una ruta '
                  'como /og.png.',
    )
    noindex = models.BooleanField(
        default=False, verbose_name='No indexar',
        help_text='Marcada, la pagina no aparece en buscadores.',
    )

    class Meta:
        verbose_name = 'Meta de ruta'
        verbose_name_plural = 'Metas por ruta'
        ordering = ['ruta']

    def __str__(self):
        return '/%s' % self.ruta


class SeoRobots(models.Model):
    """El robots.txt del sitio: una sola fila, editable como texto.

    Si no hay fila (o esta en blanco), el servidor sirve el fichero
    del build — el comportamiento de siempre —: la base solo ANYADE
    control, nunca rompe.
    """

    contenido = models.TextField(
        verbose_name='Contenido',
        help_text='Lineas tal cual: User-agent, Allow, Disallow, Sitemap.',
    )
    actualizado = models.DateTimeField(
        auto_now=True, verbose_name='Actualizado')

    class Meta:
        verbose_name = 'robots.txt'
        verbose_name_plural = 'robots.txt'

    def __str__(self):
        return 'robots.txt'

    def save(self, *args, **kwargs):
        # Un solo ejemplar: es la configuracion, no una coleccion.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def cargar(cls):
        """La fila unica, o None si nadie ha configurado nada aun."""
        try:
            return cls.objects.get(pk=1)
        except cls.DoesNotExist:
            return None
