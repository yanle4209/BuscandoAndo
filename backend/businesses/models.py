from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from categories.models import Category
from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus


# Featured tier limits PER CATEGORY
FEATURED_LIMITS = {
    '1': 3,
    '2': 3,
    '3': 3,
    '4': 3,
}

FEATURED_WEEKS_CHOICES = [
    (1, '1 semana'),
    (2, '2 semanas'),
    (3, '3 semanas'),
    (4, '4 semanas'),
]


class Business(models.Model):
    """Nucleo del negocio/servicio."""
    name = models.CharField(max_length=200, verbose_name='Nombre')
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(verbose_name='Descripcion')
    short_description = models.CharField(
        max_length=300, blank=True, default='', verbose_name='Descripcion corta'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='businesses',
        verbose_name='Categoria',
    )
    publication_status = models.ForeignKey(
        PublicationStatus,
        on_delete=models.PROTECT,
        related_name='businesses',
        verbose_name='Estado de publicacion',
    )
    operational_status = models.ForeignKey(
        OperationalStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='businesses',
        verbose_name='Estado operativo',
    )

    # === DESTACADOS ===
    is_featured = models.BooleanField(default=False, verbose_name='Destacado')
    FEATURED_TIERS = [
        ('1', 'Nivel 1 - Principal'),
        ('2', 'Nivel 2 - Alto'),
        ('3', 'Nivel 3 - Medio'),
        ('4', 'Nivel 4 - Basico'),
    ]
    featured_tier = models.CharField(
        max_length=10,
        choices=FEATURED_TIERS,
        blank=True,
        null=True,
        verbose_name='Nivel de destacado',
        help_text='Nivel de relevancia del destacado (1=principal, 4=basico)',
    )
    featured_permanent = models.BooleanField(
        default=False,
        verbose_name='Destacado permanente',
        help_text='Si esta activo, el destacado no expira.',
    )
    featured_weeks = models.PositiveIntegerField(
        choices=FEATURED_WEEKS_CHOICES,
        null=True,
        blank=True,
        verbose_name='Semanas destacado',
        help_text='Duracion en semanas del destacado.',
    )
    featured_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Inicio destacado',
    )
    featured_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fin destacado',
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado el')

    class Meta:
        verbose_name = 'Negocio'
        verbose_name_plural = 'Negocios'
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return self.name

    def clean(self):
        """Validar limites de destacados por tier y categoria."""
        super().clean()
        if not self.is_featured:
            return

        tier = self.featured_tier
        if not tier:
            return

        # Auto-set defaults for duration if not provided (e.g. from list_editable)
        if not self.featured_permanent and not self.featured_weeks:
            self.featured_permanent = True

        # Validate per-CATEGORY limit (exclude self on update)
        cat_id = self.category_id
        if cat_id:
            qs = Business.objects.filter(
                is_featured=True, featured_tier=tier, category_id=cat_id
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            current_count = qs.count()
            limit = FEATURED_LIMITS.get(tier, 0)

            if current_count >= limit:
                tier_display = dict(self.FEATURED_TIERS).get(tier, tier)
                cat_name = self.category.name if self.category else 'sin categoria'
                raise ValidationError({
                    'featured_tier': (
                        f'Limite alcanzado en categoria "{cat_name}": '
                        f'maximo {limit} destacados "{tier_display}". '
                        f'Actualmente hay {current_count}.'
                    ),
                })

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not set, and calculate featured dates."""
        from django.utils.text import slugify

        if not self.slug and self.name:
            base_slug = slugify(self.name, allow_unicode=True)
            slug = base_slug
            counter = 1
            while Business.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        # Auto-calculate featured_end_date based on weeks.
        if self.is_featured and self.featured_permanent:
            self.featured_end_date = None
            if not self.featured_start_date:
                self.featured_start_date = timezone.now()
        elif self.is_featured and self.featured_weeks:
            if not self.featured_start_date:
                self.featured_start_date = timezone.now()
            from datetime import timedelta
            self.featured_end_date = self.featured_start_date + timedelta(weeks=self.featured_weeks)
        elif not self.is_featured:
            # Clear featured dates when removing featured
            self.featured_start_date = None
            self.featured_end_date = None
            self.featured_permanent = False
            self.featured_weeks = None
        super().save(*args, **kwargs)

    @property
    def is_featured_active(self):
        """Check if the featured status is still active (not expired)."""
        if not self.is_featured:
            return False
        if self.featured_permanent:
            return True
        if self.featured_end_date and self.featured_end_date < timezone.now():
            return False
        return True

    @property
    def featured_days_remaining(self):
        """Days remaining for the featured status."""
        if not self.is_featured or self.featured_permanent:
            return None
        if not self.featured_end_date:
            return None
        remaining = (self.featured_end_date - timezone.now()).days
        return max(0, remaining)

    @property
    def is_published(self):
        return self.publication_status.slug == 'publicado'

    @property
    def featured_remaining(self):
        """Return remaining slots for this tier in same category."""
        if not self.featured_tier or not self.category_id:
            return 0
        qs = Business.objects.filter(
            is_featured=True, featured_tier=self.featured_tier,
            category_id=self.category_id
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return max(0, FEATURED_LIMITS.get(self.featured_tier, 0) - qs.count())
