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
- **`slug`**: hoy se ve en la cabecera como texto, pero no es editable
  desde el panel (cambiarlo rompería los enlaces públicos y el
  sitemap). Si se quiere editar, hay que añadirlo a `fieldsets` y
  pensarlo bien.
- **Fotos en producción**: ninguna de las 144 fichas revisadas tiene
  imagen. Si Cloudinary **no** está configurado en Render, la primera
  foto subida guardará en disco y `/media/` no la servirá (en
  producción `serve_react` excluye `media/`). Merece una comprobación
  desde el panel de Render: que `CLOUDINARY_CLOUD_NAME` esté con valor.
- **Subir fotos desde el panel**: no se ha probado el flujo completo de
  subida (solo se ha comprobado el pintado y el servido).
