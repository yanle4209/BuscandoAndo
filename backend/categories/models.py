from django.db import models


class Category(models.Model):
    """Categoría de negocios/servicios."""
    name = models.CharField(max_length=100, verbose_name='Nombre')
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Categoría padre',
    )
    icon = models.CharField(max_length=50, blank=True, default='', verbose_name='Icono')
    description = models.TextField(blank=True, default='', verbose_name='Descripción')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['name']
        unique_together = ['name', 'parent']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    @property
    def full_name(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
