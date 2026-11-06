from django.db import models
from businesses.models import Business


class BusinessContact(models.Model):
    """Información de contacto del negocio."""
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name='contact',
        verbose_name='Negocio',
    )
    phone = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Teléfono',
        help_text=(
            'Varios numeros separados por punto y coma, '
            'ej: 8095551234; 8095555678.'),
    )
    whatsapp = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='WhatsApp',
        help_text='Número con código de país, ej: +18095551234',
    )
    email = models.EmailField(blank=True, default='', verbose_name='Correo')
    website = models.URLField(blank=True, default='', verbose_name='Sitio web')
    contact_person = models.TextField(
        blank=True, default='',
        verbose_name='Contacto',
        help_text='Nombre del responsable o persona de contacto cuando el negocio no tiene teléfono/correo propio.',
    )

    class Meta:
        verbose_name = 'Contacto'
        verbose_name_plural = 'Contactos'

    def __str__(self):
        return f"Contacto: {self.business.name}"
