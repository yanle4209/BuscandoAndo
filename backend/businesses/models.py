import secrets

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from categories.models import Category
from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus


# Inventario de destacados: UNO por categoria y municipio. Ese es el
# espacio que se vende ("para cuando comience a vender los espacios"):
# cada categoria de cada municipio tiene un hueco, y un hueco ocupado no
# se vende dos veces. El tope antiguo (3 por nivel y categoria, GLOBAL)
# se retiro: agotaba el inventario a nivel pais y no protegia el hueco
# por municipio. La comprobacion vive en Business.clean() y en
# BusinessLocation.clean(); la seleccion del buscador (hasta3, uno por
# categoria) en businesses.views.featured_by_search.
DESTACADOS_POR_ESPACIO = 1

FEATURED_WEEKS_CHOICES = [
    (1, '1 semana'),
    (2, '2 semanas'),
    (3, '3 semanas'),
    (4, '4 semanas'),
]


def q_destacado_activo():
    """Q del destacado ACTIVO: marcado y no caducado.

    Mismo criterio que ``Business.is_featured_active`` y que
    ``featured-by-search``. No mira la publicacion: un destacado pagado
    reserva su espacio aunque la ficha este en borrador.
    """
    ahora = timezone.now()
    return (
        models.Q(is_featured=True)
        & (
            models.Q(featured_permanent=True)
            | models.Q(featured_end_date__isnull=True)
            | models.Q(featured_end_date__gt=ahora)
        )
    )


def destacado_en_el_espacio(category_id, municipio, exclude_pk=None):
    """El destacado activo que ya ocupa el espacio (categoria, municipio).

    Devuelve el ``Business`` ocupante o ``None`` (hueco libre). El
    municipio se compara normalizado (tildes, mayusculas): el campo es
    texto libre en la ficha. Sin municipio comparte el hueco
    ``(sin municipio)`` de geografia, igual que en los reportes.
    """
    from .geografia import SIN_MUNICIPIO, normalizar

    candidatos = (
        Business.objects.filter(q_destacado_activo())
        .filter(category_id=category_id)
        .select_related('location')
    )
    if exclude_pk:
        candidatos = candidatos.exclude(pk=exclude_pk)

    clave = normalizar(municipio or SIN_MUNICIPIO)
    for otro in candidatos:
        loc = getattr(otro, 'location', None)
        propio = normalizar(getattr(loc, 'municipality', '') or SIN_MUNICIPIO)
        if propio == clave:
            return otro
    return None


class Business(models.Model):
    """Nucleo del negocio/servicio."""
    name = models.CharField(max_length=200, verbose_name='Nombre')
    # `allow_unicode` y el help_text van en el CAMPO: el form del
    # panel valida tambien con los validadores del modelo (el
    # ``_post_clean`` del form limpia la instancia), y un
    # ``Business.formfield`` no se ejecuta jamas — ``Model`` no tiene
    # ese metodo; Django llama al ``formfield`` del campo. Sin
    # allow_unicode el panel no dejaria guardar los miles de slugs con
    # tildes que ya hay en la base.
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        allow_unicode=True,
        help_text=(
            'URL de la ficha: /business/ mas este valor. Si lo cambias, '
            'la URL anterior sigue abriendo: redirige a esta (301). En '
            'vacio se genera a partir del nombre.'),
    )
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

    # === ANUNCIO DE VIDEO ===
    # El negocio marcado deja de salir como tarjeta normal: su espacio
    # en la celda de resultados es un VIDEO, con las mismas reglas que
    # los destacados (5 km, categoria, rotacion) y solo cuando el hueco
    # no tiene destacado de pago (destacado > video > anuncio de
    # imagen). DISENO.md a1.
    is_ad = models.BooleanField(
        default=False,
        verbose_name='Anuncio de video',
        help_text='La celda de resultados pone su video en vez de su '
                  'tarjeta. Solo entra si la búsqueda no tiene destacado '
                  'de pago.',
    )
    ad_video = models.FileField(
        upload_to='anuncios/video/',
        blank=True,
        null=True,
        verbose_name='Video',
        help_text='MP4 (también WebM/MOV), ideal corto y apaisado. La '
                  'ficha debe estar publicada.',
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
        # Tres indices que en SQLite local ni se notan y en Postgres son
        # la diferencia entre leer el indice y escanear las 16 mil filas:
        # - (is_featured, featured_tier): los conteos de destacados del
        #   panel filtran exactamente por esos dos campos.
        # - (is_featured, created_at): el orden por defecto de la lista
        #   ('-is_featured', '-created_at') y el sitemap.
        # - (created_at): el filtro por fecha del panel y los listados
        #   que solo ordenan por alta.
        indexes = [
            models.Index(fields=['is_featured', 'featured_tier'],
                         name='negocio_destacados_idx'),
            models.Index(fields=['is_featured', 'created_at'],
                         name='negocio_orden_lista_idx'),
            models.Index(fields=['created_at'], name='negocio_creado_idx'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """Validar el espacio de destacado: UNO por categoria y municipio."""
        super().clean()

        # Anuncio de video: sin video no hay anuncio que pintar en la
        # celda, y el archivo tiene que ser algo que el navegador sepa
        # reproducir. Antes del atajo de destacados: el caso del
        # anuncio no es destacado y no llegaria aqui si no.
        if self.is_ad and not self.ad_video:
            raise ValidationError({
                'is_ad': (
                    'Marcaste el anuncio pero falta el video: sube un '
                    'MP4 (o desmarca la casilla).'
                ),
            })
        if self.ad_video:
            ext = (self.ad_video.name or '').rsplit('.', 1)[-1].lower()
            if ext not in ('mp4', 'm4v', 'webm', 'mov'):
                raise ValidationError({
                    'ad_video': (
                        'El video tiene que ser MP4 (también WebM/MOV): '
                        f'se recibió ".{ext}".'
                    ),
                })

        if not self.is_featured:
            return

        # Auto-set defaults for duration if not provided (e.g. from list_editable)
        if not self.featured_permanent and not self.featured_weeks:
            self.featured_permanent = True

        # El municipio vive en la ubicacion, que en el alta entra como
        # inline DESPUES del negocio: sin location no hay municipio que
        # comparar (se comprobara al editar la ubicacion, en
        # BusinessLocation.clean). Mientras tanto comparte el hueco
        # "(sin municipio)".
        loc = getattr(self, 'location', None)
        municipio = getattr(loc, 'municipality', '')
        ocupante = destacado_en_el_espacio(
            self.category_id, municipio, exclude_pk=self.pk,
        )
        if ocupante:
            cat = self.category.name if self.category_id else 'sin categoria'
            raise ValidationError({
                'is_featured': (
                    f'Espacio ocupado: la categoria "{cat}" ya tiene un '
                    f'destacado activo en este municipio: "{ocupante.name}". '
                    f'Solo se permite {DESTACADOS_POR_ESPACIO} destacado '
                    f'por categoria y municipio.'
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

        # El slug que estaba guardado ANTES de este save: si el negocio
        # cambia de slug, el anterior queda en `SlugAntiguo` para que la
        # URL vieja redirija (301) en vez de romperse. Solo hay que
        # leerlo cuando ya existe la fila.
        anterior = None
        if self.pk:
            anterior = (Business.objects.filter(pk=self.pk)
                        .values_list('slug', flat=True).first())

        super().save(*args, **kwargs)

        if anterior and anterior != self.slug:
            SlugAntiguo.objects.update_or_create(
                slug=anterior, defaults={'business': self})
        # Un slug vivo manda sobre el historial: si este negocio acaba de
        # tomar un slug que constaba como antiguo de otro, esa fila deja
        # de valer. Asi la vista y la API encuentran primero la ficha
        # real y una peticion jamas redirige a si misma.
        SlugAntiguo.objects.filter(slug=self.slug).delete()

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



class SlugAntiguo(models.Model):
    """Slug que un negocio tuvo antes: mantiene viva la URL antigua.

    Cuando se cambia el slug en el panel, el anterior queda aqui. La
    vista publica (``/business/<slug>/``) y la API (``retrieve``)
    buscan tambien en esta tabla y redirigen 301 al slug actual: el
    enlace compartido y lo que Google ya indexo siguen abriendo.

    Un slug vivo manda sobre esta tabla: ``Business.save`` borra la fila
    que coincida con su slug actual, de modo que la vista siempre
    encuentra primero la ficha real y jamas se entra en bucle.
    """

    slug = models.SlugField(
        max_length=220,
        unique=True,
        allow_unicode=True,
        verbose_name='Slug antiguo',
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='slugs_antiguos',
        verbose_name='Negocio',
    )
    creado_el = models.DateTimeField(auto_now_add=True, verbose_name='Creado')

    class Meta:
        verbose_name = 'Slug antiguo'
        verbose_name_plural = 'Slugs antiguos'
        ordering = ['-creado_el']

    def __str__(self):
        return '%s -> %s' % (self.slug, self.business.slug)


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
        ('direccion', 'Dirección'),
        ('telefono', 'Teléfono / WhatsApp'),
        ('categoria', 'Categoría'),
        ('descripcion', 'Descripción'),
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
        # "Reporte": el idioma del usuario (DISENO 15), no el tecnico.
        verbose_name = 'Reporte de usuario'
        verbose_name_plural = 'Reportes de usuarios'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_campo_display()} · {self.business.name}'



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
        null=True, blank=True,
        verbose_name='Token de firma',
        help_text='Sin token, el colaborador no puede firmar. Se puede '
                  'regenerar o borrar desde su ficha.',
    )
    token_creado_el = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Token creado el',
        help_text='Cuándo se generó el token actual. Queda vacío si no hay '
                  'token. Cambia al regenerarlo.',
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
    expira_el = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Acceso válido hasta',
        help_text='Vacío = sin caducidad. Si se vence, el token deja de '
                  'aceptar envíos y reportes aunque siga activo.',
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
        if not self.token:
            return f'{self.nombre} (sin token)'
        if not self.activo:
            return f'{self.nombre} (bloqueado)'
        if self.expira_el and self.expira_el <= timezone.now():
            return f'{self.nombre} (vencido)'
        return self.nombre

    @property
    def esta_vigente(self):
        """Activo y dentro de la fecha de caducidad (si tiene)."""
        if not self.activo:
            return False
        return self.expira_el is None or self.expira_el > timezone.now()

    def save(self, *args, **kwargs):
        # Solo se genera al crear. Asi «Borrar token» no se deshace al
        # guardar cualquier otro cambio de la ficha.
        if self._state.adding and not self.token:
            self.token = _token_nuevo()
            if self.token_creado_el is None:
                self.token_creado_el = timezone.now()
        super().save(*args, **kwargs)

    def regenerar_token(self):
        """Emite un token nuevo y mata el anterior al instante."""
        self.token = _token_nuevo()
        self.token_creado_el = timezone.now()
        self.save(update_fields=['token', 'token_creado_el'])
        return self.token

    def borrar_token(self):
        """Deja al colaborador sin firma hasta que se le genere otra."""
        self.token = None
        self.token_creado_el = None
        if not self._state.adding:
            self.save(update_fields=['token', 'token_creado_el'])


class Envio(models.Model):
    """El registro de cada envio del canal de levantamiento.

    Aqui esta la auditoria: quien firmo, que mando y que decidio el sistema
    (§11.5). Es lo que permite juzgar a un colaborador concreto y bloquear
    solo su token. El colaborador no lo lee — no hay acceso, hay envio.

    El nombre del firmante se copia al envio en ``firmante_nombre``: borrar
    al colaborador no borra la auditoria, solo deja ``colaborador`` vacio.

    ``estado`` refleja la decision del sistema, no una decision humana:

    * ``publicado``   — cumplio los obligatorios, entro a la luz;
    * ``pendiente``   — paso la validacion pero le falta algo
                        obligatorio, y ya esta en el reporte de §11.1;
    * ``rechazado``   — fallo en la puerta, no queda pendiente de nada;
    * ``duplicado``   — ya existia: se le completo lo que faltaba.
    """

    ESTADOS = [
        ('publicado', 'Publicado'),
        ('pendiente', 'Pendiente (falta lo obligatorio)'),
        ('rechazado', 'Rechazado en la puerta'),
        ('duplicado', 'Ya existia'),
    ]

    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='envios',
        verbose_name='Colaborador',
        help_text='Puede quedar vacío si el colaborador se borra; el '
                  'nombre se conserva en “Firmante”.',
    )
    firmante_nombre = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Firmante',
        help_text='Nombre del colaborador al momento del envío. Se '
                  'conserva aunque el colaborador se borre.',
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
        help_text='Que le falta al negocio para cumplir los obligatorios. '
                  'Es lo que se le devuelve al colaborador para que lo '
                  'complete.',
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
        verbose_name = 'Envío de campo'
        verbose_name_plural = 'Envíos de campo'
        ordering = ['-recibido_el']

    @property
    def firmante(self):
        """Quién firmó, aunque el colaborador ya no exista."""
        if self.firmante_nombre:
            return self.firmante_nombre
        if self.colaborador_id:
            return self.colaborador.nombre
        return '—'

    def save(self, *args, **kwargs):
        # Copia el nombre al crear el envío: el snapshot es lo que
        # sobrevive si luego se borra el colaborador.
        if not self.firmante_nombre and self.colaborador_id:
            self.firmante_nombre = self.colaborador.nombre
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_estado_display()} · {self.firmante}'


class Pospuesto(models.Model):
    """Una ficha que el editor decidio dejar aparte (los «pospuestos»).

    La decision es SUYA, no del sistema: no toca la ficha ni su
    publicacion, solo la saca de SUS listas de trabajo para que el
    reporte diga lo que esta dispuesto a hacer — hay negocios que no
    desea completar o que no se pueden completar, y estorbarle en la
    lista no ayuda.

    Es por DUENO: cada colaborador (o el admin) tiene las suyas, porque
    lo que uno pospone no le estorba al otro. No se guarda el municipio
    —sale de la propia ficha— ni el estado: el reporte lo recalcula con
    ``particionar`` en cada lectura.
    """

    negocio = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='pospuestos',
        verbose_name='Negocio',
    )
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, null=True, blank=True,
        related_name='pospuestos', verbose_name='Colaborador',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
        blank=True, related_name='pospuestos', verbose_name='Usuario',
    )
    creado_el = models.DateTimeField(
        auto_now_add=True, verbose_name='Creado el',
    )

    class Meta:
        verbose_name = 'Pospuesto'
        verbose_name_plural = 'Pospuestos'
        ordering = ['negocio__name']
        # Una sola fila por ficha y por dueno: con los dos UNIQUE de
        # abajo (y su condition) la base se encarga, aunque el codigo
        # use get_or_create.
        constraints = [
            models.UniqueConstraint(
                fields=['negocio', 'colaborador'],
                condition=models.Q(colaborador__isnull=False),
                name='pospuesto_uno_por_colaborador',
            ),
            models.UniqueConstraint(
                fields=['negocio', 'usuario'],
                condition=models.Q(usuario__isnull=False),
                name='pospuesto_uno_por_usuario',
            ),
        ]

    def __str__(self):
        quien = self.colaborador or self.usuario
        return f'{self.negocio.name} — pospuesto por {quien}'


class Cobro(models.Model):
    """Control de cobros por negocio (destacados y otros conceptos).

    Registro contable independiente del destacado: anota montos,
    conceptos y estatus SIN tocar la ficha ni el inventario de espacios
    (1 por categoria y municipio). Se gestiona desde el panel:
    ``list_editable`` cambia el estatus en la lista y las acciones lo
    hacen en bloque, igual que en Reportes de usuarios.

    ``fecha_pago`` es CONSECUENCIA del estatus, no un dato que se
    teclea: se pone sola el dia que el cobro pasa a "pagado" y se limpia
    en cuanto deja de estarlo. Por eso es de solo lectura en el form.
    """

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
        ('vencido', 'Vencido'),
        ('cancelado', 'Cancelado'),
    ]

    METODOS = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta', 'Tarjeta'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    ]

    negocio = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='cobros',
        verbose_name='Negocio',
    )
    concepto = models.CharField(
        max_length=200,
        verbose_name='Concepto',
        help_text='Que se cobra, por ejemplo: "Destacado 4 semanas - '
                  'Nivel 1".',
    )
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Monto',
        help_text='En pesos dominicanos.',
    )
    estado = models.CharField(
        max_length=12,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado',
    )
    # Lo que se VENDIO en esta venta: son los dos datos que aplican al
    # activar el destacado desde el cobro (boton en el panel). Van aqui
    # y no en la ficha porque el contrato es del cobro, no del negocio.
    nivel = models.CharField(
        max_length=10,
        choices=Business.FEATURED_TIERS,
        default='1',
        verbose_name='Nivel de destacado',
        help_text='Nivel que se aplica al activar desde este cobro '
                  '(1=principal, 4=basico).',
    )
    semanas = models.PositiveIntegerField(
        choices=FEATURED_WEEKS_CHOICES,
        default=4,
        verbose_name='Semanas de destacado',
        help_text='Duracion que se aplica al activar desde este cobro.',
    )
    fecha_cobro = models.DateField(
        default=timezone.localdate,
        verbose_name='Fecha de cobro',
        help_text='Fecha en que se registra el cobro.',
    )
    fecha_vencimiento = models.DateField(
        null=True, blank=True,
        verbose_name='Vence el',
        help_text='Si se pasa sin pagar, la accion "Vencer vencidos" del '
                  'panel lo marca como Vencido.',
    )
    fecha_pago = models.DateField(
        null=True, blank=True,
        verbose_name='Pagado el',
        help_text='Se pone sola al marcar el cobro como pagado.',
    )
    metodo = models.CharField(
        max_length=15,
        choices=METODOS,
        blank=True, default='',
        verbose_name='Metodo de pago',
    )
    nota = models.TextField(
        blank=True, default='',
        verbose_name='Nota interna',
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Creado el',
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Actualizado el',
    )

    class Meta:
        verbose_name = 'Cobro'
        verbose_name_plural = 'Cobros'
        ordering = ['-fecha_cobro', '-created_at']
        indexes = [
            models.Index(fields=['estado'], name='cobro_estado_idx'),
            models.Index(fields=['fecha_vencimiento'],
                         name='cobro_vencimiento_idx'),
        ]

    def __str__(self):
        return f'{self.negocio.name} · {self.concepto} · {self.monto}'

    @property
    def esta_vencido(self):
        """Pendiente cuya fecha de vencimiento ya paso.

        No cambia el estatus (eso lo decide el admin con la accion):
        es el aviso para la columna del listado.
        """
        return (
            self.estado == 'pendiente'
            and self.fecha_vencimiento is not None
            and self.fecha_vencimiento < timezone.localdate()
        )

    @property
    def destacado_activo(self):
        """Si la ficha del negocio esta AHORA en destacados."""
        return self.negocio.is_featured_active

    def activar_destacado(self):
        """Pone la ficha del negocio en destacados (la venta, el click).

        El nivel y las semanas salen del cobro. Valida el espacio —
        1 destacado por categoria y municipio — ANTES de tocar la base:
        si esta ocupado, ``Business.clean`` lanza ``ValidationError`` y
        no cambia nada (el admin lo enseña como mensaje de error).
        """
        negocio = self.negocio
        negocio.is_featured = True
        negocio.featured_tier = self.nivel
        negocio.featured_permanent = False
        negocio.featured_weeks = self.semanas
        negocio.featured_start_date = timezone.now()
        negocio.clean()
        negocio.save()

    def quitar_destacado(self):
        """Saca la ficha de destacados: se acabo el tiempo o el contrato."""
        negocio = self.negocio
        if negocio.is_featured:
            negocio.is_featured = False
            negocio.save()

    def save(self, *args, **kwargs):
        if self.estado == 'pagado':
            if not self.fecha_pago:
                self.fecha_pago = timezone.localdate()
        else:
            self.fecha_pago = None
        super().save(*args, **kwargs)


class Anuncio(models.Model):
    """Publicidad de la casa para la celda destacada de los resultados.

    Mientras no entre la primera venta, el espacio de destacados se
    rellena con anuncios (decision: "destacado primero, anuncio
    rellena"): la web solo pide anuncios cuando la busqueda no tiene
    destacado de pago que mostrar, asi que un negocio que pago nunca
    pierde su celda. El anuncio lleva imagen, titulo y enlace — lo
    minimo para un cuadro 2x2 con boton hacia fuera — y se gestiona
    entero desde el panel (DISENO.md a1).
    """

    class Meta:
        ordering = ['-creado']

    titulo = models.CharField(
        max_length=120,
        verbose_name='Título',
        help_text='Texto grande del anuncio.',
    )
    imagen = models.ImageField(
        upload_to='anuncios/',
        verbose_name='Imagen',
        help_text='Foto del anuncio (la celda mide 2x2: apaisada ideal).',
    )
    enlace = models.URLField(
        verbose_name='Enlace',
        help_text='A donde lleva el clic, por ejemplo la página de la '
                  'promoción.',
    )
    # Sin categoria sirve en cualquier busqueda; con categoria, solo
    # cuando se busca esa (la celda de resultados respeta el filtro de
    # categoria de la busqueda, igual que los destacados).
    categoria = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='anuncios',
        verbose_name='Categoría',
        help_text='Vacío = cualquier búsqueda.',
    )
    fecha_inicio = models.DateField(
        null=True,
        blank=True,
        verbose_name='Mostrar desde',
        help_text='Vacío = desde ya.',
    )
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name='Mostrar hasta',
        help_text='Vacío = sin fecha final.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Un click en la lista del panel lo enciende o apaga.',
    )
    creado = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado',
    )

    def __str__(self):
        return self.titulo

    def clean(self):
        if (self.fecha_inicio and self.fecha_fin
                and self.fecha_fin < self.fecha_inicio):
            raise ValidationError({
                'fecha_fin': 'La fecha final no puede ser anterior a la '
                             'inicial.',
            })

    @property
    def vigente(self):
        """Activo y dentro de su ventana de fechas (reloj del proyecto)."""
        hoy = timezone.localdate()
        return (
            self.activo
            and (self.fecha_inicio is None
                 or self.fecha_inicio <= hoy)
            and (self.fecha_fin is None or self.fecha_fin >= hoy)
        )
