# Registro de mejoras — panel de administración

> Qué se ha tocado en esta ronda, por qué y cómo deshacerlo.
> Fecha: **1 de noviembre de 2026**. La sesión anterior sigue en
> `REGISTRO_DECISIONES.md` (hasta la entrada D-14); aquí va lo hecho
> después: el despliegue verificado y la **ficha de negocio**.
>
> Orden: primero lo que estaba **roto**, luego lo **nuevo**.

---

## 1. Despliegue verificado — commit `d22a23c`

- **Qué**: se subió a `main` el commit `d22a23c` (47 ficheros) con el
  filtro de categorías en un solo desplegable, los rótulos de los dos
  desplegables y el arreglo del municipio con paginación. GitHub
  auto-desplegó en Render.
- **Cómo se verificó**:
  - CI en verde en los **tres** trabajos: backend (262 tests),
    frontend (`oxlint` + build) y Android (`gradlew testDebugUnitTest`).
  - `https://buscandoando.onrender.com/api/health/` devuelve el commit
    nuevo.
  - `/admin/login/` responde 200 y los **13** estáticos que pide dan 200.
  - El CSS del panel pasa de `886f28b90b6b` a `ff353f2fd44e` y aparece
    `buscandoando_filtros.668d704bf387.js`, que `base_site.html` ya
    referencia: con `CompressedManifestStaticFilesStorage` una
    referencia sin manifest rompe la página entera, y eso no pasó.
- **Sobre el admin "roto" que se había visto**: el código desplegado
  **no estaba roto**. Producción era idéntica a `HEAD` (mismo hash de
  CSS) y ese código pintaba bien con `DEBUG=false` y el manifest de
  producción en una réplica local. Lo más probable es una ventana de
  deploy o el arranque en frío de la máquina gratis.
- **Ojo con las credenciales**: las de producción **no** son las de
  local. El usuario es `admin` (minúsculas) y la contraseña vive en
  Render → *Settings* → *Environment* → `DJANGO_SUPERUSER_PASSWORD`.
  Además hay un **freno de login** (`ThrottleLoginAdmin`): 5 fallos
  desde la misma IP → 10 minutos de bloqueo.

**Cómo deshacerlo**: `git revert d22a23c`.

---

## 2. La ficha de negocio se caía con 500 (arreglado)

- **El síntoma**: `/admin/businesses/business/<id>/change/` devolvía
  `Server Error (500)` — en local. La página entera del formulario.
- **La causa**:
  `ValueError: Must supply cloud_name in tag or in configuration`.
  `STORAGES['default']` estaba **siempre** en
  `cloudinary_storage.storage.MediaCloudinaryStorage`, así que el
  primer `.url()` de cualquier foto pedía el `cloud_name` a Cloudinary.
  Sin las variables `CLOUDINARY_*` en el entorno (no hay ninguna en
  esta máquina) la excepción se produce **al pintar** el
  `BusinessImageInline`, y se cae la ficha entera.
- **Dónde está**: `backend/config/settings.py`, `STORAGES['default']`.
- **El arreglo**: el storage de media es Cloudinary **solo si hay
  `CLOUDINARY_CLOUD_NAME`**; sin él cae a `FileSystemStorage` y se
  define `MEDIA_ROOT`. Con credenciales —producción— **no cambia nada**.
- **Colateral que también se arregló**: el test
  `config.tests.SeoTests.test_la_ficha_titula_con_nombre_categoria_y_lugar`
  esperaba `og.png` en el `og:image`. Salía por accidente: el fixture
  **sí** tiene foto (`la_receta.webp`) y la vista
  (`backend/views.py:96`) solo caía al fallback porque el `.url()`
  reventaba. Ahora sale la foto de verdad, que es lo correcto. El
  fallback sigue cubierto por el test del índice.
- **Por qué afecta a producción**: hoy **no** (de las 144 fichas
  revisadas por la API pública, ninguna tiene fotos). Pero era una
  mina: la primera foto que alguien subiera en un entorno sin
  credenciales tumbaría la ficha y la vista pública.

**Cómo deshacerlo**: volver a poner
`'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'`
fijo en `settings.py` y restaurar `assertIn('og.png', html)` en el test.

---

## 3. `/media/` se servía en local (nuevo)

- **Qué**: `backend/config/urls.py` sirve ahora `/media/` con
  `django.views.static.serve`, **solo** cuando el storage de media es
  el de disco (misma condición que en el punto 2).
- **Por qué**: con Cloudinary las fotos son de `res.cloudinary.com` y
  `/media/` no existe (así estaba comentado en `urls.py`). Pero con el
  storage en disco nadie servía esas rutas: la cabecera de la ficha
  saldría con la foto rota.
- **Verificado**: `GET /media/business_images/2026/09/estadio_1.webp`
  → 200 (57 KB) y la imagen carga en el navegador sin errores de
  consola.

**Cómo deshacerlo**: borrar el bloque `if ... endswith('FileSystemStorage')`
de `urls.py`.

---

## 4. `procedencia` y las fechas eran invisibles (arreglado)

- **El problema**: `Business` tiene el campo `procedencia` (4 valores:
  `manual`, `importado`, `levantado`, `verificado`), que es "el único
  campo nuevo que pide R5" según su propio comentario en
  `businesses/models.py`. La API pública **lo sirve**, pero en el panel
  **no aparecía en ningún `fieldsets`**, o sea que no se veía ni se
  podía marcar como *Verificado por humano*. Lo mismo con `created_at`
  y `updated_at`, que estaban en `readonly_fields` pero fuera de todo
  fieldset.
- **El arreglo**: fieldset nuevo **«Origen y fechas»** en
  `BusinessAdmin` (`backend/businesses/admin.py`), con `procedencia`
  (editable) y las dos fechas (solo lectura).
- **Comprobado en el navegador**: el fieldset aparece como cuarto, tras
  «Destacados».

**Cómo deshacerlo**: quitar el fieldset de la tupla `fieldsets`.

---

## 5. Cabecera de la ficha (nueva)

Hasta ahora la ficha era el Django de fábrica: un muro de campos y,
debajo, cuatro inlines. Ahora abre con una tarjeta:

| Pieza | Qué muestra |
|---|---|
| **Foto** | La primera de `images` (96×96, recorte redondeado). Si no hay, un «Sin foto» |
| **Nombre** | El del negocio |
| **Pastillas** | Estado de publicación · estado operativo · categoría · municipio · «Destacado nivel N» |
| **Metadatos** | Procedencia · Creado · Actualizado · Slug |
| **Botón** | «Ver en el sitio» → `/business/<slug>` (la ruta real de `frontend/App.jsx`), en pestaña aparte |

- **Ficheros**: `backend/templates/admin/businesses/business/change_form.html`
  (la cabecera) y `backend/static/admin/css/buscandoando_admin.css`
  (`.ba-ficha*` y las variantes `ba-badge--<slug-de-estado>`).
- **Sin `<script>` inline**: el CSP del proyecto es `script-src 'self'`,
  y la cabecera no lleva JS. Los atributos `style` sí están permitidos
  (`style-src 'self' 'unsafe-inline'`), pero aquí no se usa ninguno.
- **Cada pastilla lleva un color por slug** (`--publicado`, `--abierto`,
  `--por-cerrar`…). Un slug nuevo que se cree en la BD cae en el pastel
  neutro `.ba-badge`, que también se lee.
- **En móvil** la cabecera se apila y el botón pasa a todo el ancho.
- **Solo en el cambio, no en el alta**: el bloque va envuelto en
  `{% if original %}`, así que `/add/` no lleva cabecera (comprobado:
  «Añadir Negocio» sin `.ba-ficha`).

**Cómo deshacerlo**: vaciar `change_form.html` a como estaba (solo el
`<script>` de `business_admin.js`) y borrar el bloque
`/* ===== FICHA DE NEGOCIO — CABECERA ===== */` del CSS.

---

## 6. Tres detalles del modelo que costaron descubrir

Vale la pena dejarlos escritos, porque son trampas para quien toque el
template:

1. **`BusinessLocation.municipality` es un `CharField`**, no una FK.
   `{{ loc.municipality.name }}` sale **vacío**; hay que escribir
   `{{ loc.municipality }}`. Lo mismo `province`.
2. **`location` y `contact` son `OneToOneField`**: `obj.location` es el
   objeto (o no existe), **no** un manager. `obj.location.first()`
   revienta con `AttributeError`.
3. **`images` y `hours` sí son FK**: ahí sí hay manager
   (`obj.images.first`).
4. **`is_published` es una propiedad**, no un método: `obj.is_published`
   sin paréntesis (también en los templates).

---

## Pendientes y por decidir

- ~~**El nombre sale dos veces**~~ — **resuelto**. Venía del bloque
  `content_subtitle` de `admin/base.html:102` (Django pinta
  `<h2>{{ subtitle }}</h2>` justo bajo el `<h1>`), y la cabecera nueva
  lo repetía dentro de la tarjeta. Se vacía el bloque en
  `change_form.html` con `{% block content_subtitle %}{% endblock %}`,
  que es el hueco que Django deja para eso. Ningún test lo vigila
  (grep de `subtitle`/`<h2>` en `tests.py`: sin resultados), y
  verificado en el navegador: solo queda el nombre dentro de `.ba-ficha`.
  **Ojo**: el autoreloader de `runserver` solo vigila ficheros Python,
  así que un cambio de plantilla exige reiniciar el servidor.
- ~~**`slug` editable**~~ — **resuelto y probado** (3/nov, **273 tests
  en verde**). El campo va en `fieldsets` («Informacion Basica», justo
  tras `name`), y cambiarlo no rompe nada: el modelo `SlugAntiguo`
  guarda el slug anterior en cada `save()` (y borra la fila si el slug
  vuelve a ser el vigente), y tanto la vista pública (`serve_react`)
  como la API (`BusinessViewSet.retrieve`) responden **301** al slug
  actual. Lo no publicado sigue siendo 404 (no se filtra nada); la
  redirección no pasa por `registrar()`, para no contar dos veces la
  visita. Verificado en vivo: `/business/verificacion-slug-temp/` →
  301 `Location: /business/belleza-total-salon` (y lo mismo en
  `/api/businesses/`), y tras borrar la fila de prueba la URL vuelve a
  404. La cabecera muestra «Tambien responde a: <slug viejo>» (máx.
  5), comprobada en el navegador junto al campo y su ayuda.
  **Trampa que costó descubrir**: `Model` no tiene `formfield` (lo
  tiene el campo), así que un `Business.formfield`/`BusinessImage.formfield`
  era código muerto — de ahí que el texto de ayuda de la foto no
  saliera nunca. Y el form del admin valida además con los
  validadores del modelo (`_post_clean` → `full_clean()`): tanto
  `allow_unicode` como el `help_text` tienen que ir en el **campo**
  del modelo, no en `formfield_overrides` del admin (se probó así y se
  revirtió). Migraciones: `businesses/0010-0011`,
  `business_images/0004`.
- **Fotos en producción** — el usuario confirma el 3/nov que **ya
  funcionan**. Diagnóstico previo del fallo, por si vuelve:
  - Escaneo de la API pública: **0 de 738 fichas con foto** (ningún
    `image_url` en el listado — o la subida es muy reciente, o está en
    una ficha que el listado no devuelve, que solo enseña publicadas).
    Para cerrarlo hará falta una ficha concreta con foto visible.
  - `GET /media/business_images/...` en producción → **404**
    (`serve_react` excluye `media/` fuera de DEBUG).
  - `/admin/login/` responde 200: el panel sí está desplegado, se
    puede probar desde el navegador.
  Causas encadenadas: (a) el 500 de `save_related` (NameError de
  `date`) impidió guardar fotos con horario válido — corregido en
  `9b1796e` y ya desplegado, pero **no reprobado en producción**;
  (b) sin Cloudinary configurado en Render, la foto se guarda en el
  disco efímero del contenedor; (c) `serve_react` no sirve `/media/`
  en producción, así que aunque guardara daría 404; (d) cada
  redeploy borra ese disco. **La solución es configurar
  `CLOUDINARY_CLOUD_NAME`/`API_KEY`/`API_SECRET` en Render** (los
  `image.url` apuntarían al CDN y ya no pasarían por `serve_react`);
  el código de soporte ya está. Si el arreglo fue subir las
  credenciales a Render, la ficha de prueba confirmará que `image_url`
  sale de `res.cloudinary.com`.
- ~~**Los filtros del listado se restablecen al volver**~~ —
  **resuelto y probado** (3/nov, **275 tests**). Desde un listado
  filtrado Django enlaza cada fila con `?_changelist_filters=...` y el
  redirect tras «Guardar» ya lo reexpandía en la query de verdad; la
  fuga era la **miga «Negocios»** del formulario de cambio, que
  apuntaba al changelist pelado — al volver un nivel se perdían
  búsqueda y filtros. Arreglado con el tag oficial
  `{% add_preserved_filters %}` en el bloque `breadcrumbs` de
  `change_form.html` (solo reexpande si el destino es ese changelist;
  sin filtros devuelve la URL tal cual). Verificado en vivo: guardar
  con `?q=Total` aterriza en `/admin/businesses/business/?q=Total` con
  el filtro puesto, y la miga lleva `.../business/?q=Total`. Cubierto
  por la clase `FiltrosDelListadoSeConservan` (2 tests); el helper de
  POST del panel se extrajo a `_datos_del_formulario_admin` y lo
  comparten con los tests del slug.
- ~~**Subir fotos desde el panel**~~ — **resuelto y probado** (2/nov).
  El flujo completo (fila nueva en el inline → subir → guardar →
  `/media/` la sirve) **daba 500**: `save_related` de
  `businesses/admin.py` usaba `date.fromordinal(...)` para marcar los
  festivos sin tener `date` importado (`NameError`). Solo saltaba al
  guardar un negocio con horarios de día válido, así que ningún test
  lo alcanzaba (262 en verde antes y después) y en producción nunca
  se vio porque no hay admin allí. Corregido con
  `from datetime import date`. Verificado en el navegador: fila
  insertada, imagen convertida a WebP 1200x675, `/media/` responde y
  consola sin errores. **Nota de diagnóstico**: los `NameError` no
  aparecían en la consola de `runserver` (Django los manda a
  `mail_admins`, sin configurar); hizo falta un segundo servidor con
  `DEBUG=1` para leer el traceback.
- ~~**Herramienta de levantamiento** (pedido recurrente, 3/nov): (a)
  categoría creable con validación, (b) imágenes con las mismas reglas
  que el admin, (c) imagen obligatoria~~ — **resuelto y probado**
  (4/nov, **290 tests en verde**, desplegado en local con las tres
  piezas verificadas en el navegador).
  - **Backend** (`businesses/levantamiento.py`): la bandera
    `categoria_nueva` dispara `_categoria_nueva()`, que valida el
    nombre al momento (obligatorio), dedupea por `name__iexact`,
    genera el slug con `slugify(allow_unicode)` y, si ese slug ya es
    de otra categoría, reutiliza esta (`IntegrityError` → se busca);
    sin la bandera solo se busca, como siempre (el importador la
    sigue creando, porque el nombre viene de OSM). Las fotos entran
    por `request.FILES.getlist('imagenes')` y pasan por `_abrible()`
    (Pillow en la puerta: «tiene que ser una imagen»),
    `_validar_imagenes()` (techo `MAX_IMAGES_PER_BUSINESS = 5`,
    contando las existentes en el camino de completar y en el de
    duplicado) y `_guardar_imagenes()` en los tres caminos (alta,
    duplicado, completar). La obligatoria: alta sin fotos → «Una
    ficha nueva necesita al menos una foto»; completar con la ficha
    en 0 fotos → «Esta ficha no tiene ninguna foto: hay que mandar al
    menos una»; si la ficha ya tiene ≥1, no hace falta mandar. El
    envío pasa a **multipart**: `_horario` acepta el JSON como texto
    y `_booleano()` lee `'true'/'1'/'on'/'yes'`; `None` no viajan.
    `Envio.datos['imagenes']` guarda los nombres que llegaron y el
    detalle `?ficha=` añade `imagenes: N` para que el cliente calcule
    `5 − N` sin mandarlas. `imagen` no entra en `faltantes_de` (las
    11 etiquetas siguen sin contarla).
  - **Frontend** (`Levantamiento.jsx` / `.css`): el desplegable de
    categoría tiene «➕ Crear categoría nueva…» (centinela
    `__nueva__`) que abre un campo de texto sobre el **mismo**
    `datos.categoria`, con nota de validación; sin nombre no se
    envía (`listo` lo vigila) y tras el éxito se recarga
    `/categories/` para que aparezca ya en la lista. Tarjeta
    «Fotos»: nota con las que ya tiene la ficha y las que caben,
    miniaturas de las pendientes (objectURL con ✕ para quitarlas),
    contador `existentes + nuevas / 5`, etiqueta de subir que pasa a
    «Máximo 5 fotos» y se deshabilita al techo — **sin bloquear el
    envío** —, y el aviso obligatorio en el pie junto al de token y
    nombre. `enviar()` manda **FormData** (horario → JSON en texto,
    casillas → `'true'`/`'false'`, fotos en `imagenes` una por
    parte) y la rejilla de dos columnas gana la fila `fotos`.
  - **Trampa que costó descubrir**: la instancia axios manda
    `Content-Type: application/json` por defecto y axios 1.x, con
    esa cabecera puesta, **convierte el FormData a JSON**
    (`formDataToJSON`): los campos viajaban perfectos pero **las
    fotos se perdían por el camino**, y el servidor rechazaba con
    «Una ficha nueva necesita al menos una foto» pareciendo que el
    formulario no mandaba nada. El POST va ahora con cabecera
    `multipart/form-data` propia (y el porqué quedó anotado en
    `axios.js`, que antes decía «sin subidas multipart, verificado»).
  - Verificado en el navegador (4/nov): alta con 1 foto → «✓
    Aceptado y publicado», ficha creada **con la categoría nueva**
    (slug `panaderia-prueba-cat`) y la foto convertida a
    `business_images/2026/11/calle-principal.webp`, con
    `Envio.datos['imagenes']` registrado; el desplegable ya
    enseña «Panaderia Prueba Cat» sin recargar; el techo de 5 deja
    la etiqueta deshabilitada con «Llegaste al máximo» y el envío
    sigue activo (5 fotos guardadas en otra ficha); y una ficha con
    1 foto existente se puede completar **sin mandar fotos** (la
    foto queda intacta). Fichas de prueba en la base local, por si
    quieres mirarlas: **16292** (categoría nueva + 1 foto), **16293**
    (5 fotos), **16294** (pendiente → completada) y la categoría
    «Panaderia Prueba Cat» — se borran cuando quieras.
  - Tests: **+15** → **290 en verde**: fotos en alta (obligatoria,
    WebP + auditoría, techo de 5, archivo que no es imagen), multipart
    (horario como texto, `cerrado` como casilla), categoría (bandera
    crea, dedupe mayúsculas, slug reutilizado, sin nombre se
    rechaza) y completar (sin foto cuando no hay, con foto ya puesta,
    techo, `imagenes` en el reporte).
