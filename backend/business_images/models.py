from django.db import models
from django.core.exceptions import ValidationError
from businesses.models import Business

MAX_IMAGES_PER_BUSINESS = 5


class BusinessImage(models.Model):
    """Imagen de un negocio (hasta 5 por negocio)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Negocio',
    )
    image = models.FileField(
        upload_to='business_images/%Y/%m/',
        verbose_name='Imagen',
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Pie de foto',
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Orden',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagen del negocio'
        verbose_name_plural = 'Imagenes del negocio'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.business.name} - Imagen {self.order}"

    def clean(self):
        """Validar maximo 5 imagenes por negocio."""
        super().clean()
        if not self.business_id:
            return
        qs = BusinessImage.objects.filter(business_id=self.business_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.count() >= MAX_IMAGES_PER_BUSINESS:
            raise ValidationError(
                f'Maximo {MAX_IMAGES_PER_BUSINESS} imagenes por negocio. '
                f'Este negocio ya tiene {qs.count()}.'
            )
