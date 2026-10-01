import secrets

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

    # === PROCEDENCIA (R5, DISENO.md seccion 10) ===
    # Lo que viene del servicio entra marcado: el usuario ve la calidad de
    # la ficha sin que se pierda el control. Es el UNICO campo nuevo que
    # pide R5 — lo pendiente es calculado, no se guarda.
    PROCEDENCIAS = [
        ('manual', 'Manual'),
        ('importado', 'Importado (automatico)'),
        ('levantado', 'Levantado por colaborador'),
        ('verificado', 'Verificado por humano'),
    ]
    procedencia = models.CharField(
        max_length=12,
        choices=PROCEDENCIAS,
        default='manual',
        verbose_name='Procedencia',
        help_text='De donde salio la ficha. "importado" se anade solo, para '
                  'senalar lo que nadie ha revisado todavia.',
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


class Correction(models.Model):
    """Aviso de un visitante de que un dato de un negocio esta mal.

    Lo dispara el boton "Corregir" de las tarjetas del frontend, que abre
    un formulario modal. NO requiere login: cualquiera puede avisar.

    Por eso la separacion de lectura/escritura es el punto delicado de este
    modelo: quien lo rellena solo puede crear uno, y el listado, el estado
    y las notas quedan para el admin (ver CorrectionViewSet).
    """

    # Coincide 1:1 con las opciones del <select> del formulario, y con los
    # datos que muestra BusinessCard: si anades un dato a la tarjeta,
    # anadelo aqui para que se pueda reportar.
    CAMPOS = [
        ('nombre', 'Nombre del negocio'),
        ('direccion', 'Direccion'),
        ('telefono', 'Telefono / WhatsApp'),
        ('categoria', 'Categoria'),
        ('descripcion', 'Descripcion'),
        ('estado', 'Estado (abierto/cerrado)'),
        ('horario', 'Horario'),
        ('otro', 'Otro'),
    ]

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('revisada', 'Revisada'),
        ('aplicada', 'Aplicada'),
        ('descartada', 'Descartada'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='corrections',
        verbose_name='Negocio',
    )
    campo = models.CharField(
        max_length=20,
        choices=CAMPOS,
        verbose_name='Dato incorrecto',
    )
    mensaje = models.TextField(
        verbose_name='Que esta mal / cual es el dato correcto',
        help_text='Texto que lee el admin.',
    )
    estado = models.CharField(
        max_length=12,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado',
    )
    nota_admin = models.TextField(
        blank=True,
        default='',
        verbose_name='Nota interna del admin',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creada el')
    resolved_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Resuelta el'
    )

    class Meta:
        verbose_name = 'Correccion'
        verbose_name_plural = 'Correcciones'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_campo_display()} · {self.business.name}'

    @property
    def esta_resuelta(self):
        return self.estado in ('aplicada', 'descartada')


def _token_nuevo():
    """El token de un colaborador.

    Aleatorio y opaco: no lleva informacion dentro, asi que robarselo no
    descubre nada. Con eso basta porque su unico uso es FIRMAR un envio
    (§11.5) — nunca abrir nada.
    """
    return secrets.token_urlsafe(32)


class Colaborador(models.Model):
    """Quien firma los envios del canal de levantamiento.

    **No es un usuario.** No entra a nada, no lee nada, no tiene permisos:
    solo tiene un token con que firmar (§11-i: "no hay acceso, hay
    envio"). Esa distincion es la que permite construir el canal completo
    sin montar autenticacion, y la que deja bloquear a UNO —apagar su
    token— sin cerrar el canal a los demas.
    """

    nombre = models.CharField(max_length=120, verbose_name='Nombre')
    # Editable=False: se genera en save() y no se teclea. En el admin sale
    # como solo lectura para poder copiarlo y entregarselo.
    token = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        verbose_name='Token de firma',
    )
    municipio = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Municipio',
        help_text='Solo informativo: el municipio de cada envio lo declara '
                  'el propio envio, no el token.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Apagarlo bloquea a este colaborador sin tocar a los demas.',
    )
    creado_el = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    ultimo_envio = models.DateTimeField(
        null=True, blank=True, verbose_name='Ultimo envio',
    )

    class Meta:
        verbose_name = 'Colaborador'
        verbose_name_plural = 'Colaboradores'
        ordering = ['nombre']

    def __str__(self):
        estado = '' if self.activo else ' (bloqueado)'
        return f'{self.nombre}{estado}'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = _token_nuevo()
        super().save(*args, **kwargs)


class Envio(models.Model):
    """El registro de cada envio del canal de levantamiento.

    Aqui esta la auditoria: quien firmo, que mando y que decidio el sistema
    (§11.5). Es lo que permite juzgar a un colaborador concreto y bloquear
    solo su token. El colaborador no lo lee — no hay acceso, hay envio.

    ``estado`` refleja la decision del sistema, no una decision humana:

    * ``publicado``   — cumplio el trio, entro a la luz;
    * ``pendiente``   — paso la validacion pero le falta el trio, y ya
                        esta en el reporte de §11.1;
    * ``rechazado``   — fallo en la puerta, no queda pendiente de nada;
    * ``duplicado``   — ya existia: se le completo lo que faltaba.
    """

    ESTADOS = [
        ('publicado', 'Publicado'),
        ('pendiente', 'Pendiente (falta el trio)'),
        ('rechazado', 'Rechazado en la puerta'),
        ('duplicado', 'Ya existia'),
    ]

    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.PROTECT,
        related_name='envios',
        verbose_name='Colaborador',
    )
    negocio = models.ForeignKey(
        Business,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='envios',
        verbose_name='Negocio',
    )
    estado = models.CharField(
        max_length=12,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Decision del sistema',
    )
    motivos = models.JSONField(
        default=list, blank=True,
        verbose_name='Motivos',
        help_text='Por que se rechazo. Solo cuando estado es "rechazado".',
    )
    faltan = models.JSONField(
        default=list, blank=True,
        verbose_name='Campos que faltan',
        help_text='Que le falta al negocio para cumplir el trio. Es lo que '
                  'se le devuelve al colaborador para que lo complete.',
    )
    datos = models.JSONField(
        default=dict, blank=True,
        verbose_name='Datos recibidos',
        help_text='Copia literal de lo que llego, para auditar.',
    )
    ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='IP',
    )
    recibido_el = models.DateTimeField(
        auto_now_add=True, verbose_name='Recibido el',
    )

    class Meta:
        verbose_name = 'Envio'
        verbose_name_plural = 'Envios'
        ordering = ['-recibido_el']

    def __str__(self):
        return f'{self.get_estado_display()} · {self.colaborador.nombre}'
