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
    phone = models.CharField(max_length=20, blank=True, default='', verbose_name='Teléfono')
    whatsapp = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='WhatsApp',
        help_text='Número con código de país, ej: +573001234567',
    )
    email = models.EmailField(blank=True, default='', verbose_name='Correo')
    website = models.URLField(blank=True, default='', verbose_name='Sitio web')

    class Meta:
        verbose_name = 'Contacto'
        verbose_name_plural = 'Contactos'

    def __str__(self):
        return f"Contacto: {self.business.name}"
