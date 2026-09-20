from django.db import models


class OperationalStatus(models.Model):
    """Estado operativo del negocio (abierto, cerrado, etc.)."""
    name = models.CharField(max_length=50, unique=True, verbose_name='Nombre')
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True, default='', verbose_name='Descripción')
    color = models.CharField(max_length=7, default='#22c55e', verbose_name='Color (hex)')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Estado Operativo'
        verbose_name_plural = 'Estados Operativos'
        ordering = ['order']

    def __str__(self):
        return self.name
