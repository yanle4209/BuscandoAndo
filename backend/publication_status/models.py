from django.db import models


class PublicationStatus(models.Model):
    """Estado de publicación de una entrada."""
    name = models.CharField(max_length=50, unique=True, verbose_name='Nombre')
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True, default='', verbose_name='Descripción')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Estado de Publicación'
        verbose_name_plural = 'Estados de Publicación'
        ordering = ['order']

    def __str__(self):
        return self.name
