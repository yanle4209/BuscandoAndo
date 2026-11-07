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
- **Levantamiento: la categoría no se confirmaba y «Actualizar» no
  se notaba** — **resuelto y probado** (5/nov, **291 tests**). Dos
  defectos reportados en producción:
  - **«Crear categoría nueva» parecía no hacer nada**. Causa doble:
    (a) la API `/categories/` está **paginada** (12 por hoja) y el
    desplegable solo cargaba la primera — en producción eso
    escondía «Talleres Mecánicos», «Tecnología», «Tiendas» y
    «Veterinaria», y si el usuario tecleaba una de esas el
    servidor la **reutilizaba en silencio** (dedupe `name__iexact`)
    sin crear nada ni decirlo; (b) no había **ninguna
    confirmación**: la respuesta no contaba qué pasó con la
    categoría. Arreglo: `cargarCategorias()` recorre **todas las
    hojas** (sigue `next`), el backend responde `categoria_creada`
    / `categoria_reusada` (con el nombre canónico) en los tres
    éxitos — `_categoria_nueva` ahora devuelve si creó—, y
    `Resultado` lo dice en castellano: «Se creó la categoría X y ya
    aparece en el desplegable» / «La categoría X ya existía: se usó
    esa y no se creó otra», con la categoría **preseleccionada** en
    el desplegable tras el envío. Además la categoría ahora solo
    se crea **si el envío entero se acepta** (las fotos validan
    antes): un rechazo no deja hojas sueltas en la tabla.
  - **«Actualizar» no daba señal**. El refresco sí ocurría
    (`GET /pendientes/`), pero la lista vieja se conserva a
    propósito mientras llega la nueva (para que no parpadee) y si
    los datos no cambiaban **no se veía nada**. Ahora el botón se
    deshabilita y dice «Actualizando…» mientras vuela la petición
    (con `cursor: not-allowed`), y la línea de «Cargando…» acompaña.
  - Verificado en el navegador (5/nov): clic en «Actualizar» →
    `GET /api/pendientes/` + etiqueta «Actualizando…» observada
    con MutationObserver; desplegable con las **14** categorías
    locales (antes 12, perdía la página 2); alta con bandera →
    «✓ Aceptado y publicado» + «Se creó la categoría Panaderia
    Confirmacion…» preseleccionada; reenvío del mismo nombre →
    «✓ Aceptado: ficha existente completada» + «…ya existía: se
    usó esa» sin duplicar (15 categorías, ninguna segunda). Datos
    de prueba borrados: 1 ficha (16295), 2 fotos, 2 envíos y la
    categoría.
  - Tests: **+1** → **291 en verde** (asserts de `categoria_creada`
    / `categoria_reusada` en los casos de creación y de reuso, y
    test nuevo: bandera + envío rechazado → no se crea la
    categoría).
- **Levantamiento: el teléfono admitía un solo número** —
  **resuelto y probado** (5/nov, **297 tests**). Negocios con más de
  uno no cabían: un solo campo en el formulario y `contact.phone`
  (CharField de 20 caracteres) guardaba un solo número. Diseño
  elegido: **varios campos en el formulario → una cadena** con la
  convención de OSM (`;`, `,`, `/` o `|`), que es como ya venían
  los teléfonos del importador — sin modelo nuevo ni tabla aparte:
  - **Formulario**: cada número en su propio campo, con «+ Añadir
    teléfono» (techo de **5**, el mismo razonable que las fotos; al
    llegar el botón pasa a «Máximo 5 teléfonos») y ✕ para quitar
    cada fila. Al enviar se une con `'; '`; los campos vacíos no
    cuentan. La nota recuerda que sin teléfono la ficha queda en el
    reporte y, si solo hay un campo, invita a añadir otro.
  - **Servidor**: `contact.phone` pasa de 20 a **200** caracteres
    (migración `business_contacts/0004_alter_businesscontact_phone`,
    con help_text para el panel); `partir_telefonos()` parte la
    cadena y `validar()` exige que **todos** los números sean
    llamables (uno malo rechaza el envío entero, mensaje
    «El telefono no tiene un formato valido.» de siempre) y añade
    «Se aceptan hasta 5 telefonos.» si se pasa del techo. El trío
    `nombre + telefono + punto` no cambia: basta con que la cadena
    no esté vacía. `enriquecer()` y el alta guardan la cadena tal
    cual (siguen sin sobrescribir lo que ya había).
  - **Fichas públicas**: helper nuevo `src/telefono.js`
    (`partirTelefono`) y las tres superficies — tarjeta, modal y
    ficha completa — pintan **cada número con su enlace `tel:`
    propio** separados por «·» (un `href` con dos números pegados
    no marca a nadie).
  - **Al abrir una ficha** en el levantamiento la cadena se vuelve
    a repartir en sus campos, y «limpiar» la deja en un campo
    vacío; el chip del reporte (`restanFicha`) mide si algún campo
    tiene número.
  - Verificado en el navegador (5/nov): campo único + botón; dos
    clics → 3 campos con ✕; a 5 → «Máximo 5 teléfonos»
    deshabilitado; quitar → 4. Envío real con dos números → POST
    con `telefono: "809-555-1111; 809-555-2222"` → «✓ Aceptado y
    publicado» y `contact.phone` guardado **exactamente** esa
    cadena. Ficha pública `/business/prueba-telefonos-varios`:
    «Teléfono: 809-555-1111 · 809-555-2222» con dos `<a href="tel:…">`;
    tarjeta en el inicio: misma fila con los dos enlaces; modal:
    dos píldoras de contacto. Al elegir la ficha en el
    desplegable, la cadena se reparte en dos campos con sus valores.
    Datos de prueba borrados: 1 ficha (16296), 1 foto y 1 envío →
    **16.287 fichas** como al principio.
  - Tests: **+6** → **297 en verde**: `partir_telefonos` (varios
    separadores, vacíos), `telefonos_valido` (cadena válida, un
    malo entre buenos), puerta (`validar` acepta cadena y rechaza
    un número malo), techo de 5, y alta con
    `telefono='809-555-1111; 809-555-2222'` → `contact.phone`
    entero + publicado.
- **El levantamiento: una ficha publicada seguía saliendo en la
  lista de pendientes** — **resuelto y probado** (5/nov, **298
  tests**). Regla que pidió el editor: si al mandar una
  actualización el sistema ya deja la ficha actualizada y
  publicada, no tiene por qué seguir apareciendo en la lista,
  **aunque le falte algún campo**: si ya están los requeridos, no
  hay necesidad que sigan apareciendo. El detalle de
  `/api/pendientes/?municipio=` metía en `fichas` toda ficha con
  campos faltantes, **publicadas incluidas** (las ordenaba al
  final para «completarlas»), así que un envío que publicaba
  dejaba la ficha en el desplegable «Negocio a completar» y, al
  recargar, otra vez como pendiente.
  - **Servidor** (`businesses/views.py`): *pendiente = no
    publicado*. El detalle (`fichas`), su `con_pendientes`, el
    desglose `por_campo` y el contador `con_pendientes` de cada
    fila del listado se calculan **solo sobre fichas sin
    publicar**, de modo que fila ⇒ botón ⇒ lista ⇒ chips dicen
    exactamente lo mismo. `en_revision` sigue contando todo lo no
    publicado. Lo publicado con extras pendientes ya no aparece
    en ningún sitio del reporte.
  - **Navegador** (`Levantamiento.jsx`): la fila verde de
    confirmación de sesión se marca ahora cuando el envío deja la
    ficha **publicada** (antes solo si no faltaba nada: la que se
    publicaba con extras ni se ponía verde ni salía de la lista);
    la nota de éxito deja de prometer a ciegas — para la
    publicada dice «ya no sale en la lista de pendientes, aunque
    le falten extras, y la que dejaste queda en verde», y los
    envíos que siguen en revisión solo dicen que el reporte se
    actualizó (el renglón de arriba ya explica que la ficha
    sigue ahí).
  - Verificado en el navegador (5/nov): Moca con 148 fichas y
    111 pendientes; se abrió «Academia de las Fuerzas Armadas»
    (le faltaba el teléfono), se puso un número → «✓ Aceptado y
    publicado» con «Todavía le falta: dirección, whatsapp…» → la
    ficha salió **sola** del desplegable, la fila quedó en
    verde, el resumen pasó a 110/110 y los chips a 110. **Al
    recargar**: ni select ni fila — borrada del todo. Datos
    restaurados (la ficha 44 volvió a `en-revision` sin teléfono
    ni foto) → **16.287 fichas**.
  - Tests: **+1** → **298 en verde**: circuito completo
    `test_un_envio_que_publica_no_deja_pendiente` (envío →
    reporte); se reescribió
    `test_las_que_hay_que_publicar_van_primero` →
    `test_una_publicada_con_faltans_no_vuelve_a_la_lista` (la
    regla vieja estaba al revés: la publicada iba la última
    *dentro* de la lista) y los contadores que pasaban de 3 a 2
    en Moca (fila y detalle).
- **El levantamiento: con el municipio sin nada pendiente, la
  columna derecha se vaciaba y parecía rota (arreglado)** —
  **Qué pasaba**: con la regla nueva, en producción el municipio
  del token quedó con `con_pendientes = 0` (todo lo que tenía
  faltantes ya estaba publicado) y, como el detalle solo se carga
  cuando `con_pendientes > 0`, la tarjeta «Lo que falta en tu
  municipio» se quedaba con **solo el título y la línea del
  resumen**: «toda la sección de la derecha desapareció». El
  reporte estaba en regla (no queda nada por completar), pero no
  lo decía y parecía que algo se había caído.
  - **Arreglo** (`Levantamiento.jsx` + clase `.lev-vacio` en el
    CSS): si existe la fila, `total > 0` y
    `con_pendientes = 0`, la tarjeta pinta en verde —con el mismo
    verde del resto del reporte— «✓ No queda nada por completar en
    tu municipio: todo lo que tenía faltantes ya está publicado.»
    El reporte nunca desaparece: se explica. Si además hay fichas
    `en_revision` sin faltantes, el resumen de arriba ya los
    cuenta («esperando publicarse») y no se duplica el mensaje.
  - **Verificado en el navegador (5/nov)**: token temporal para
    «(sin municipio)» (3 fichas, todas publicadas) → título +
    resumen + aviso en verde, sin selector, sin botón y sin
    lista — exactamente la pantalla de producción pero explicada;
    con el token Demo Local (Moca, 111 pendientes) nada cambia
    (select de 112, 111 filas, sin aviso). Token temporal
    borrado al terminar.
  - **Tests**: sin cambios de servidor → **298 en verde**;
    `oxlint` limpio, build + `collectstatic` (21).
- **El «atrás» desde una ficha completa perdía los filtros del home
  (arreglado)** — **Qué pasaba**: en producción, al pulsar «Ver ficha
  completa» el visitante llegaba a `/business/:slug` y, al volver con
  el botón de atrás, Home remontaba desde `ESTADO_INICIAL`: sin texto
  de búsqueda, sin categoría, sin página y sin el modal abierto —
  «te envía a la página sin filtros aplicados ni nada». La causa:
  la vista (filtros, punto, página, modal) vivía solo en el
  `useReducer` de `Home.jsx` (y el municipio en el `localStorage`),
  así que la URL del historial no tenía nada que restaurar.
  - **Arreglo** (`frontend/src/pages/Home.jsx`): la URL pasa a ser
    el estado de la vista. Al montar, `leerVista()` y
    `estadoDesdeVista()` leen `?text=`, `?category=`, `?page=`,
    `?lat=`/`?lng=` y `?ficha=` y los devuelven como estado inicial
    (el punto de la URL entra por la misma puerta que «elegir
    municipio»: con GPS cerca manda el GPS y con GPS lejos se queda
    el suyo). Un efecto escribe la vista a la URL con `replace` —sin
    ensuciar el historial— y **solo escribe el punto elegido**
    (`destino`): la posición exacta del GPS jamás entra en la URL,
    que es dato personal, no un estado que compartir en un enlace.
    Abrir el modal empuja `?ficha=` y cerrarlo lo quita con
    `replace`: al volver de la ficha completa el modal se reabre solo
    (y «atrás» con el modal abierto lo cierra, como es habitual en
    la web). Si la consulta ya contestó y el slug no está en los
    resultados, el parámetro se descarta para no dejar un modal
    muerto que se abriera solo más adelante.
  - **Verificado en el navegador (6/nov)**: con Moca +
    «restaurante» (3 resultados) la URL queda
    `?lat=…&lng=…&text=restaurante`; al pulsar una tarjeta se añade
    `&ficha=restaurante-el-conuco`; «Ver ficha completa» → **atrás**
    → mismos 3 resultados, el input con «restaurante» y el modal
    **reabierto** con El Conuco; la X del modal quita solo
    `&ficha=` dejando los filtros; y una visita nueva a `/` sin
    parámetros queda limpia (sin fugas de la URL).
  - **Tests**: sin cambios de servidor → **298 en verde**;
    `oxlint` limpio, build (`Home-DeSY9edv.js`) + `collectstatic`
    (21) + runserver reiniciado.
- **El levantamiento: los obligatorios pasan a ser cinco (nombre,
  dirección, teléfono, imagen + punto) y las publicadas con faltantes
  van a su propia lista** — **resuelto y probado** (6/nov, **300
  tests**). Regla que pidió el editor y que cambia las dos entradas
  anteriores: publicar ya no exige el «trio» `nombre + teléfono +
  punto` sino **cinco campos** —nombre, dirección, teléfono, imagen y
  punto—; con eso completo la ficha **se publica aunque le falten el
  resto** (horario, WhatsApp, correo, web, descripción…), sale de la
  lista de revisión y pasa a una **lista aparte dentro de la misma
  tarjeta**: «Publicadas con faltantes», cuyos campos «se podrán
  rellenar más adelante». Una ficha sin foto ya **no** se publica,
  tampoco (el formato de importación no trae fotos: lo recargado
  espera en revisión).
  - **Servidor** (`businesses/pendientes.py`): `OBLIGATORIOS` con
    los cinco campos; `faltantes_de()` cuenta ya `imagen` (hay foto
    o no); `particionar()` reparte en tres cubos —`revision`
    (falta ≥1 obligatorio o sin publicar), `publicadas` (publicada,
    obligatorios listos y falta ≥1 opcional) y `completas` (sale en
    ninguna lista)—; `contar_pendientes()` marca `en_obligatorio`
    por chip y pone los obligatorios primero; `publicar_si_cumple()`
    exige los cinco. `views.py`: la fila del listado mide
    `con_revision`/`con_publicadas` sobre los cubos, el detalle
    manda `fichas` + `publicadas` y calcula `por_campo` sobre las
    dos listas, y el prefeteche trae `hours` e `images` (sin la
    foto, `imagen` se contaría mal). Comentarios actualizados en
    `masivo`, `levantamiento`, `ingreso`, `validacion`,
    `importar_municipio` y `cargar_fichas`. `models.py`: los textos
    de `Envio.estado`/`faltan` dicen «lo obligatorio» — migración
    `0012_alter_envio_estado_alter_envio_faltan`.
  - **Navegador** (`Levantamiento.jsx` / `.css`): `OBLIGATORIOS` y
    `CAMPOS` (12 con `imagen`); la tarjeta espera si hay algo en
    cualquiera de las **dos** listas; resumen con los dos
    contadores («146 en revisión, 2 publicadas con faltantes»);
    chips con «bloquea» en los cinco obligatorios, ordenados
    primero; selector = revisión + publicadas (evita un valor
    huérfano al abrir una publicada); **segunda lista clicable**
    (`abrirFichaPorId`, extraído de `elegirFicha`) que abre el
    mismo formulario; avance medido sobre las dos listas; `imagen`
    en `lleno` con las fotos que la ficha ya tiene; fila verde
    **solo** para la publicada completa (la que queda con faltantes
    no se pinta verde); `Resultado` explica los dos casos —«sale de
    la lista de revisión y pasa a la de publicadas con faltantes» /
    «ya no sale en ninguna lista, y la que dejaste queda en
    verde»—; el vacío cubre las dos listas.
  - **Verificado en el navegador (6/nov)**: Moca con 148 fichas →
    «146 en revisión, 2 publicadas con faltantes, 111 esperando
    publicarse», chips Imagen 146 / Teléfono 111 / Dirección 69
    primero con «bloquea», «En revisión» (146 filas) +
    «Publicadas con faltantes» (Belleza Total Salon y Restaurante
    El Conuco). Clic en una publicada → formulario rellenado
    (select sincronizado, WhatsApp/Correo/Web en amarillo, «Esta
    ficha ya tiene 4 fotos»). Envío de **Animal Farm SRL** (solo le
    faltaba la foto) → «✓ Aceptado y publicado» + «…sale de la
    lista de revisión y pasa a la de publicadas con faltantes»,
    sin verde, y tras el refresco aparece en la segunda lista
    (145/3). Completándole WhatsApp + horario + descripción →
    «…ya no sale en ninguna lista, y la que dejaste queda en
    verde», fila verde «completada ✓ Sin nada pendiente» en la
    lista de revisión y la segunda lista vuelve a 2. Consola sin
    errores. Datos restaurados (Animal Farm: `publicado` sin foto,
    WhatsApp, horario ni descripción; 2 envíos borrados) →
    **146/2/148** como al principio.
  - **Tests**: **+2** → **300 en verde** —
    `test_una_publicada_sin_foto_vuelve_a_la_revision`,
    `test_una_importada_con_foto_se_publica_al_completarse` (y
    renombres: `test_faltar_lo_obligatorio_no_rechaza`,
    `test_los_obligatorios_son_nombre_direccion_telefono_imagen_y_
    punto`, `test_se_publica_en_cuanto_cumple_lo_obligatorio`,
    `con_pendientes` → `con_revision`/`con_publicadas`). `oxlint`
    limpio, build + `collectstatic` + runserver reiniciado.
- **El levantamiento: filtrar por categoría y posponer fichas** —
  **resuelto y probado** (6/nov, **317 tests**). Dos cosas que pidió
  el editor para poder TRABAJAR con la lista en la mano: (1)
  **filtrar por categoría** —«si me apetece solo trabajar las
  escuelas, pues las selecciono y trabajo con estas»—; (2)
  **posponer** los negocios que no desea completar o que no se
  pueden (da igual cuál de los dos motivos): salen de SUS listas a
  una tercera lista «Pospuestos», guardada en el servidor por
  dueno, reversible con «Retomar».
  - **Servidor** (`businesses/`): modelo `Pospuesto` (`negocio` +
    `colaborador`/`usuario`, únicos en pareja; migración
    `0013_pospuesto`); `GET /api/pendientes/?categoria=<slug>` con
    `sin-categoria` para las que no tienen — un solo `particionar()`
    reparte listas **y** desglose `categorias`, así que el número del
    desplegable y el de la lista nunca discordar; la categoría
    elegida se añade al desplegable aunque tenga 0 trabajo (si no,
    al posponerla entera el `select` saldría en blanco); `pospuestos`
    solo con las que aún deban algo (`con_trabajo`), `total`
    absoluto, y `con_revision`/`con_publicadas`/`en_revision`/
    `por_campo` descuentan pospuestos — la fila del listado gana
    `con_pospuestos`, que su gate de espera incluye; `POST
    /api/pospuesto/` `{ficha, pospuesto}` con la misma puerta que el
    GET (`_acceso_reporte`: el token manda sobre la sesión) y
    `_le_toca` por municipio — posponer es **por dueno**, lo que uno
    aparta no le estorba al otro; `PospuestoAdmin` en el panel.
  - **Navegador** (`Levantamiento.jsx` / `.css`): estado `categoria`
    (se resetea al salir); desplegable «Categoría» con conteos por
    opción entre el resumen y las listas — al cambiarlo solo se
    recarga el DETALLE (el renglón del municipio sigue diciendo lo
    suyo); resumen con rama «categoría X — N fichas…»; chips, avance
    y listas miden la categoría; botón «Posponer» en las filas de
    las dos listas (oculto en la abierta, en las verdes y en las
    publicadas: los publicados no llevan botón) y lista
    «Pospuestos» con chip apagado y «Retomar»; los vacíos distinguen
    municipio / «siguen pospuestas» / categoría; el botón
    «Actualizar» también espera si solo quedan pospuestos.
  - **Verificado en el navegador (6/nov)**: desplegable con 14
    categorías que suman 148; filtrar Escuelas → «Moca (Espaillat) —
    categoría Escuelas — 35 fichas, 35 en revisión, 0 publicadas con
    faltantes, 33 esperando publicarse», lista con 35 filas y chips
    solo de escuelas (Imagen 35 / Teléfono 33); «Posponer» en
    Academia de Ingles Global → baja a 34 y aparece «Pospuestos»
    (chip «pospuesta» + «Retomar»), con el resumen en 34;
    «Retomar» → vuelve a 35 y la lista desaparece; «Todas las
    categorías» → 148/146/2 de siempre; consola sin errores. Datos
    restaurados (0 pospuestos, sin filtro).
  - **Arreglo posterior (6/nov): «Posponer» no hacía nada con el
    admin abierto** — con la sesión de `/admin/` en el mismo dominio,
    DRF (autenticación de sesión por defecto) rechazaba el POST con
    `403 CSRF Failed: CSRF token missing`: el axios no mandaba el
    token y el index no repartía la cookie. Arreglado en dos sitios:
    `serve_react` llama a `get_token()` al servir el index (reparte
    la cookie `csrftoken`) y `api/axios.js` la copia en cada
    petición como cabecera `X-CSRFToken` — con token de colaborador
    y sin sesión no hace falta y no estorba. Además las fichas
    **publicadas** ya no llevan «Posponer» (ni en «Publicadas con
    faltantes» ni en las publicadas de «En revisión»). Verificado
    con sesión de admin + token en el navegador: el POST sale con
    `x-csrftoken` y responde 200 (la ficha baja a «Pospuestos» y
    «Retomar» la devuelve); publicadas sin botón (0 de 2 y 0 de 37);
    consola limpia.
  - **Tests**: **+17** → **317 en verde** — clase
    `FiltroYPospuestosTests`: filtro, desglose, casillero
    `sin-categoria`, resumen, chips, posponer/retomar, por dueno
    (admin y colaborador no se pisan), 403/401/400, completa no
    pospuesta, filtro + pospuestos a la vez, categoría entera
    pospuesta que sigue en el desplegable y regresión CSRF del botón
    (sesión de admin: 403 sin la cabecera, 200 con ella).
    `oxlint` limpio, build + `collectstatic` + migración local +
    runserver reiniciado.
