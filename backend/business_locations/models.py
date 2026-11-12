from django.core.exceptions import ValidationError
from django.db import models
from businesses.models import Business, destacado_en_el_espacio


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
    referencias = models.CharField(
        max_length=300, blank=True, default='',
        verbose_name='Referencias',
        help_text='Ej: frente a la parada de bus, al lado de la farmacia. '
                  'Sirve para llegar a pie; no sustituye las coordenadas.'
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
        # El filtro de municipio del panel y el arbol provincia-municipio
        # del sidebar hacen un DISTINCT sobre estas 16 mil filas en CADA
        # carga del listado. Sin indice Postgres lo escanea entero; con
        # el, lee el indice y listo.
        indexes = [
            models.Index(fields=['municipality'],
                         name='ubicacion_municipio_idx'),
        ]

    def __str__(self):
        return f"{self.business.name} - {self.street}"

    def clean(self):
        """El municipio cierra el hueco del espacio de destacado.

        En el alta el negocio se valida SIN ubicacion (el inline entra
        despues), asi que aqui, con el negocio ya enlazado, es donde se
        puede comprobar su municipio contra la regla "1 destacado por
        categoria y municipio" (Business.clean hace lo propio al editar
        la ficha).
        """
        super().clean()
        if not self.business_id:
            return
        negocio = self.business
        if not negocio.is_featured:
            return
        ocupante = destacado_en_el_espacio(
            negocio.category_id, self.municipality, exclude_pk=negocio.pk,
        )
        if ocupante:
            raise ValidationError({
                'municipality': (
                    f'Espacio ocupado: la categoria de "{negocio.name}" '
                    f'ya tiene un destacado activo en este municipio: '
                    f'"{ocupante.name}". Solo se permite UN destacado '
                    f'por categoria y municipio.'
                ),
            })

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
