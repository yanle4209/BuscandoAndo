from django.db import models
from businesses.models import Business


class BusinessLocation(models.Model):
    """Ubicacion y direccion del negocio (República Dominicana)."""
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name='location',
        verbose_name='Negocio',
    )
    street = models.CharField(
        max_length=200, default='', verbose_name='Calle y número',
        help_text='Ej: Av. Winston Churchill #12'
    )
    sector = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Sector',
        help_text='Ej: Piantini, Naco, Zona Colonial'
    )
    municipality = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Municipio',
        help_text='Ej: Santo Domingo, Santiago'
    )
    district = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Distrito Municipal',
        help_text='Ej: Distrito Nacional'
    )
    province = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Provincia',
        help_text='Ej: Distrito Nacional, Santiago'
    )
    postal_code = models.CharField(
        max_length=10, blank=True, default='',
        verbose_name='Código Postal',
        help_text='Ej: 10100'
    )
    country = models.CharField(
        max_length=50, default='República Dominicana', verbose_name='País'
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Latitud',
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Longitud',
    )

    class Meta:
        verbose_name = 'Ubicacion'
        verbose_name_plural = 'Ubicaciones'

    def __str__(self):
        return f"{self.business.name} - {self.street}"

    @property
    def full_address(self):
        parts = [self.street]
        if self.sector:
            parts.append(self.sector)
        if self.municipality:
            parts.append(self.municipality)
        if self.province:
            parts.append(self.province)
        if self.postal_code:
            parts.append(self.postal_code)
        parts.append(self.country)
        return ', '.join(parts)

    @property
    def lat(self):
        return float(self.latitude) if self.latitude else None

    @property
    def lng(self):
        return float(self.longitude) if self.longitude else None
