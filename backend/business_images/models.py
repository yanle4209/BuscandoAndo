from django.db import models
from django.core.exceptions import ValidationError
from businesses.models import Business

from .processing import process_image

MAX_IMAGES_PER_BUSINESS = 5


class BusinessImage(models.Model):
    """Imagen de un negocio (hasta 5 por negocio)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Negocio',
    )
    image = models.ImageField(
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

    def save(self, *args, **kwargs):
        """Guarda la foto ya procesada: tamaño fijo + recorte + WebP.

        Solo cuando entra un archivo NUEVO (todavía sin subir): una
        imagen ya guardada que se re-guarda no se vuelve a procesar,
        y un valor que solo es una URL (los scripts de carga) se queda
        exactamente igual.
        """
        campo = self.image
        if campo and not campo._committed and getattr(campo, '_file', None) is not None:
            self.image = process_image(campo.file)
        super().save(*args, **kwargs)

    def formfield(self, **kwargs):
        """Texto de ayuda en el admin.

        Va por ``formfield`` y no por el campo: así no cambia la
        definición del modelo y no hace falta migración.
        """
        kwargs.setdefault(
            'help_text',
            'Se recorta al tamaño fijo (1200x675) y se convierte a WebP '
            'automáticamente. Hasta 5 fotos por negocio.',
        )
        return super().formfield(**kwargs)

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
