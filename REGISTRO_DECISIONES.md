# Registro de decisiones — sesión de revisión y finalización

> Registro de las decisiones tomadas durante la revisión asistida
> (inicio: 28–29/oct 2026), para que el dueño pueda consultarlas y
> revertirlas. Cada entrada dice **qué**, **por qué** y **cómo
> deshacerlo**. Orden cronológico inverso (lo último, arriba).

---

## Bugs menores del frontend — CERRADOS (D-2026-10-29/11)

- **Decisión**: el dueño pidió atacarlos. Commit `02ebfd6` (6 ficheros,
  +108/−22). Los cinco estaban en el informe de la auditoría de frontend
  y se habían dejado fuera de la limpieza a propósito (D-04).
- **1. `MapOverlay` — `setTimeout` sin limpiar**: el fade de 400 ms volaba
  por fuera del `setInterval` y no se cancelaba al desmontar → dos
  `setState` posteriores a la desmontaje. Arreglado guardando el id.
- **2. `axios` sin `timeout`**: una petición colgada dejaba el esqueleto de
  carga **para siempre** (no hay timeout natural que lo saque). Techo de
  **15 s**. No rompe nada lento: todo el frontend manda JSON, **sin
  subidas multipart** (verificado con grep en los 28 ficheros de `src/`).
- **3. `Home` — paginación sin recorte**: la cuenta del servidor puede
  **bajar** entre visitas (una ficha sale de zona, se borra o cambia de
  estado) → te quedabas en una página vacía que pintaba "sin resultados"
  **falso**, del que no se sale con "Siguiente" porque no hay siguiente.
  Ahora `pageNum > paginas` → se vuelve a la última página buena.
  **Premisa verificada contra el servidor**: `page=99` de Moca devuelve
  0 resultados con `count: 38` (4 páginas reales).
- **4. Guards de obsolescencia** en `BusinessDetail` y en
  `elegirFicha` de `Levantamiento`: mismo patrón **numerado** que ya
  usaba `Home` (`peticionRef`), no se inventó uno nuevo. Cubre el `.then`,
  el `.catch` (el aviso viejo) y el `.finally` (el "cargando" lo apagaba
  la petición vieja mientras la nueva volaba).
- **5. `SearchBar` montada DOS veces** (escritorio y móvil, una la esconde
  el CSS): cada instancia hacía **su** petición a `/categories/` en cada
  carga. Las categorías suben a `Home` y llegan por prop. Además el
  `autoFocus` era de las dos: el último montado se llevaba el foco, que
  era la **móvil** — en teléfono abría el teclado al cargar.
- **Verificación** (no solo lint): build real servido por Django
  (`runserver` + `frontend/dist`) y probado en navegador: carga **sin
  errores de consola**, **1 sola** petición a `/categories/` (antes 2),
  búsqueda a 5 km de Moca → **38 resultados / 12 tarjetas**,
  `featured-by-search` disparado y paginación a página 2 correcta. Además
  oxlint limpio, `vite build` OK y **262 tests de backend en verde**.
- **Ojo — hallazgo colateral, NO tocado**: el 500 local de
  `/api/businesses/` con fichas que tienen imagen es
  `ValueError: Must supply cloud_name` — la limitación ya documentada en
  `.env.example` (sin credenciales de Cloudinary en local). **No es una
  regresión**; en producción no ocurre. Para probar en local levanté el
  servidor con `CLOUDINARY_CLOUD_NAME=buscandoando-local` (solo construye
  la URL, no llama a la red).
- **Sigue abierto** (fuera de los cinco acordados): el reset de scroll de
  `Home` apunta a `.right-panel` pero el contenedor que scrollea de
  verdad es `.right-results-scroll` — observado en la prueba (sigue en
  734 px al cambiar de página). → **Cerrado después** en `b47086e`
  (cubre los tres caminos: `.right-results-scroll`, `.right-panel` y el
  documento en móvil).

---

## Fase 3 — Producto (DISENO §7) — EN CURSO

### D-2026-10-29/10 — §7.4 cerrado: el destino NO se reanuda con GPS
- **Decisión**: dar el ítem por **verificado y cerrado**, sin tocar código.
- **Por qué**: R3.6 literal. En `Home.jsx`, `restaurarMunicipio()` solo se
  invoca en los **callbacks de error** del GPS (sin soporte / denegado).
  Si el GPS responde, el dispatch `'gps'` con `modo === 'espera'` pasa a
  GPS y el `localStorage` **ni siquiera se lee**. Dentro de la sesión, en
  modo destino `restaurado`, la siguiente posición sí cede (≤5 km → GPS
  por R3.1; >5 km → sigue la cabecera).
- **Matiz corregido del informe del agente**: el municipio se **guarda**
  en `elegirMunicipio()` (cualquier elección manual), no "solo tras fallo
  de GPS"; el fallo de GPS es solo una de las dos vías de **lectura**.
- **Registrado en**: `DISENO.md` §7 fila 4.

### D-2026-10-29/09 — §7.2 medido: el mecanismo está completo, falta dato
- **Decisión**: no tocar código de cobertura; el pendiente es **de dato**,
  y queda documentado con cifras en `DISENO.md` §7.2-medido.
- **Verificado** (scripts en temp, BD local):
  - `GET /api/pendientes/` funciona: **403** anónimo · **401** token
    inválido · **200** listado (159 filas = padrón 158 + "sin municipio")
    · **200** detalle (Moca: 148 fichas, 111 sin teléfono, agrupado por
    campo con el trío primero) · `?ficha=` puebla el formulario.
  - **Deduplicación §10-d funciona**: `validacion.duplicado()` cruza el
    importador (`masivo.py` / `importar_municipio`) antes de publicar, y
    la base **no tiene duplicados reales**: 0 pares mismo nombre+municipio
    a <100 m. Los 1.412 nombres repetidos son cadenas con sucursales
    legítimas (Shell ×45, Texaco ×43, Banreservas ×38…).
- **Cifras clave**: 16.287 fichas · 1.554 publicadas (9,5 %) · 14.733 en
  revisión · **100 % con punto** · **14.733 sin teléfono** (el único campo
  del trío que falta en todas) · FASE1: 3.886 fichas → 452 publicadas,
  3.434 sin teléfono · **16 municipios del padrón sin fichas** · 5
  destacados en total (2 en FASE1).
- **Acciones que quedan (para el dueño, en orden)**: ① levantar teléfono
  en FASE1; ② `importar_municipio --todos` para los 16 vacíos; ③ marcar
  destacados (§7.3, ya con efecto real); ④ reparto de correctores.
- **Ojo**: la BD local **no es** la de producción (16.462 fichas / 1.391
  publicadas según los documentos). Las cifras de arriba son de la local;
  las de prod hay que medirlas allá.

### D-2026-10-29/08 — Diagnóstico del token: es fine-grained SIN escritura
- **Estado**: los **dos** tokens del dueño autentican como `yanle4209`
  y ven el repo, pero el push da **403**.
- **Prueba hecha**: `GET /repos/yanle4209/BuscandoAndo` reporta
  `permissions.push=True` (eso refleja los permisos del **usuario**, no
  los del token). La prueba definitiva fue un `PUT /contents/README.md`
  con contenido **idéntico** (no crea commit): devolvió
  **403 "Resource not accessible by personal access token"** → el token
  **no tiene `Contents: Read and write`**.
- **Arreglo**: GitHub → Settings → Developer settings → Tokens → el token
  → *Repository permissions* → **Contents: Read and write** → Save. (O un
  token clásico con alcance `repo`.)
- **Pendiente**: push de los 4 commits + `REGISTRO_DECISIONES.md`.
- **Aviso**: ambos tokens pasaron por el chat → **revocarlos** y generar
  uno nuevo cuando termine.

### D-2026-10-29/07 — Orden: primero §7.2 (cobertura de datos)
- **Decisión**: atacar primero la cobertura por municipio; §7.4
  (confirmación GPS) después; §7.3 (destacados) queda atada a §7.2.
- **Por qué**: elección del dueño en la pregunta de alcance.
- **Cómo deshacer**: reordenar la cola.

### D-2026-10-29/06 — El token de GitHub del dueño no sirve para push
- **Estado**: el token autentica (`yanle4209`) pero da **403 al
  push** (faltan permisos de escritura: `repo` en classic, o
  Contents: read+write en fine-grained). Los 3 commits están en
  **local**, sin push.
- **Acción**: el dueño corrige el alcance del token; después push
  (disparará autoDeploy a producción). **Pendiente.**
- **Aviso dado**: el token pasó por el chat → conviene revocarlo y
  generar otro al terminar.

---

## Fase 2 — Limpieza y calidad — COMPLETADA

### D-2026-10-29/05 — `frontend/public/robots.txt` NO se borra
- **Decisión**: mantenerlo, contra la recomendación inicial del
  informe.
- **Por qué**: es el **respaldo del build** que lee
  `_robots_efectivo()` (`backend/views.py`) cuando la fila
  `SeoRobots` de la BD está en blanco; lo exige el test
  `test_fila_en_blanco_vuelve_al_build`. Borrarlo rompería el
  backend. Queda documentado en `frontend/README.md`.
- **Cómo deshacer**: nada que deshacer.

### D-2026-10-29/04 — Frontend: muerto fuera, bugs menores NO
- **Se borró**: `public/diagnose.html`, `public/test-images.html`
  (se servían en producción), `diagnose.html` (raíz),
  `public/icons.svg`, `src/assets/{hero.png, react.svg, vite.svg}`;
  props `highlighted`/`level`/`cover` + CSS `.biz-card--highlighted`;
  bloques de horarios y "Sitio web" de BusinessModal (inalcanzables:
  `BusinessListSerializer` no trae `hours` ni `website`) + su CSS;
  estado `selected` (siempre null) en Home; condicional muerto
  `hayReporte` en Levantamiento (siempre `true` en la pantalla de
  trabajo).
- **NO se tocaron** los bugs menores del informe (MapOverlay
  setTimeout, timeout de axios, clamp de paginación, guards de
  obsolescencia, SearchBar doble) — decisión del dueño; siguen
  abiertos como posible tarea futura. → **Cerrados después**: ver
  D-2026-10-29/11.
- **Por qué**: alcance elegido por el dueño: "archivos + código
  muerto".
- **Commit**: `19e4f0e`.

### D-2026-10-29/03 — Código muerto del backend fuera (accounts incluida)
- **Se borró** (respaldo en
  `C:\Users\herli\AppData\Local\Temp\opencode\buscandoando_limpieza_2026-10-29\`):
  la app `accounts` completa (no instalada, sin `AUTH_USER_MODEL`,
  importaba `authtoken` inexistente, aceptaba `role` del cliente),
  `config/users_admin.py` (import roto), `templates/index.html`
  (sin uso), `sample_businesses*.json` (0 referencias).
- **Por qué**: pedido explícitamente por el dueño + verificado con
  grep que nada lo referenciaba.
- **Cómo deshacer**: copiar del respaldo o `git checkout ecffe5a^ -- backend/accounts`.

### D-2026-10-29/02 — Arreglos de código (backend)
- `STATUS_NAMES` gana `cerrado-permanente` → las fichas así marcadas
  dejaban de salir como "Sin estado" (`businesses/serializers.py`).
- `help_text` del WhatsApp +57 (Colombia) → +1 (RD), con migración
  `business_contacts/0003`.
- `settings.py`: fuera `DEFAULT_FILE_STORAGE` (deprecada; manda
  `STORAGES['default']`).
- Docstring de `BusinessViewSet`: decía 10 km, el radio es 5.
- **Por qué**: bugs/errores reales detectados en la revisión.
- **Commits**: `ecffe5a`.

### D-2026-10-29/01 — Infraestructura de repo y docs
- `README.md` reescrito: describía una API que no existe
  (`/api/accounts/*`, `/api/reviews/`, `/api/favorites/`,
  `/api/search/`), un frontend "próximamente" y credenciales
  `admin/admin123` que ningún comando crea (`setup_admin` exige
  `DJANGO_SUPERUSER_PASSWORD`).
- `13b62bb9-*.md` → `AUDITORIA_PRE_LANZAMIENTO.md`;
  `94a83219-*.png` → `marca_origen.png`.
- `.env.example` completo (todas las variables de settings) y honesto:
  **Django no carga `.env`** (no hay python-dotenv — decisión:
  no añadir la dependencia; se documenta el uso por entorno).
- `requirements.txt` **fijado** a las versiones verificadas en verde
  (recomendación de la propia AUDITORIA §8). Actualizar = cambiar la
  versión, correr la suite, commit.
- `frontend/README.md`: plantilla de Vite → documentación real.
- **Commits**: `ecffe5a`, `90baff3`.

---

## Fase 1 — Estabilizar y verificar — COMPLETADA

### D-2026-10-29/E3 — Entorno restaurado
- Instalados con winget: **Python 3.14.7** (la que usaba el
  proyecto), **Node.js 26.13.0**, **Git 2.56.0.3**.
- `venv` del backend recreado (el viejo apuntaba a un Python 3.14
  desaparecido) y dependencias instaladas.
- Ajustes de máquina: ejecución de PowerShell `RemoteSigned`
  (CurrentUser — sin ellos npm no corre), `safe.directory` para el
  repo de D:, identidad git `yanle4209 <yanle4209@users.noreply.github.com>`
  (la del historial), credencial de GitHub en el Gestor de
  credenciales (token actualmente sin permisos de push, ver D-06).

### D-2026-10-29/E2 — Verificación de línea base: EN VERDE
- `oxlint` limpio · `vite build` OK (index 264,7 kB / MapView 159,9 kB)
  · `manage.py check` 0 problemas · `makemigrations --check` limpio
  · `collectstatic` OK · **262 tests de backend OK** (36 s).
- Los 297 tests del CI son la referencia documentada (262 backend +
  Android + frontend lint/build).
- **Cómo repetir**: `cd frontend && npm ci && npm run lint && npm run build`,
  luego `cd ../backend && venv\Scripts\python.exe manage.py test`.

---

## Pendientes heredados que siguen abiertos (no tocados)

- **DISENO §7.2** cobertura por municipio · **§7.3** destacados
  (atada) · **§7.4** confirmación GPS → Fase 3.
- **Bugs menores frontend** (informe del agente): ver D-04.
- **MIGRACION_SERV00.md**: migración opcional a serv00 (registro en
  revisión); hoy manda el puente Render+Neon (DISENO §16).
- **Hallazgos "sin corregir" de AUDITORIA_SEGURIDAD §8**: comodín
  `.onrender.com` en ALLOWED_HOSTS (render.yaml), sin techo en
  `GET /api/pendientes/` ni `POST /api/interes/`, throttling solo en
  proceso (sin CACHES). Bajos, documentados.

---

## Empaquetado Android + cierre de sesión (D-2026-10-29/12)

- **Decisión del dueño**: "termina los trabajos, toma tú las decisiones,
  registra todo, y al final empaqueta la app Android y exportala al
  escritorio."
- **APK de release entregado**: `C:\Users\herli\Desktop\BuscandoAndo-v2026-10-29.apk`
  (2,29 MB). Firma **verificada** con `apksigner verify`: certificado
  propio `CN=BuscandoAndo, O=Herling Rodriguez, C=DO` (SHA-256
  `1bea8be6…908ac`), el mismo `.jks` de `android/keystore/` — quien ya
  tenga la app instalada podrá actualizarla sin cambiar de certificado.
  API por defecto: `https://buscandoando.onrender.com/api/` (producción).
- **Instalación de herramientas (winget, aprobada por el dueño)**:
  JDK **Temurin 21.0.12.1** + Android **SDK cmdline-tools** en
  `%LOCALAPPDATA%\Android\Sdk` (donde apunta `local.properties`),
  licencias aceptadas con `sdkmanager --licenses`, instalados
  `platform-tools`, `build-tools;37.0.0` y `platforms;android-37.0`.
- **Decisión sobre `compileSdk 37`**: el paquete del repositorio se
  llama `platforms;android-37.0` (no `android-37`); el SDK 37.1/37.2
  también existen pero no hacen falta para compilar contra 37.
  `gradlew assembleRelease` → **BUILD SUCCESSFUL** en 3m52s, R8+shrink
  activo, único aviso: deprecación de `Locale(String)` en
  `HomeScreen.kt:2731` (cosmético, sin acción).
- **Commits de la sesión (9 en total, todos en `origin/main`)**:
  `ecffe5a`, `90baff3`, `19e4f0e`, `3326a3e`, `02ebfd6` (5 bugs),
  `7b86f6e` (registro D-11), `b47086e` (reset de scroll), `5db7678`
  (registro D-12) y el commit que cierra este propio apartado.
- **Verde final**: oxlint limpio, `vite build` OK, `manage.py check`
  + `makemigrations --check` sin cambios y **262 tests de backend en
  verde** (corridos tras el último cambio de código).

### Lo que queda y DEPENDE DEL DUEÑO (no decidible por mí)

1. ~~**Push a `origin/main` bloqueado (403)**~~ → **RESUELTO
   (mismo día)**: el dueño revocó los dos tokens que pasaron por el chat
   y creó uno nuevo *fine-grained* con **Contents: Read and write**
   (guardado en el Gestor de credenciales, sin pasar por el chat). Push
   hecho: `c4f9019..5db7678` (8 commits) y **Render desplegó solo**
   (`autoDeploy`): producción en `5db7678`, sirviendo el mismo bundle que
   el build local (`index-CCUJUoyB.js`) y `/api/health/` en verde.
   Diagnóstico original por si vuelve a pasar: `PUT /contents/` con
   contenido idéntico → 403 *"Resource not accessible by personal access
   token"* (no era la rama ni el repo: era el permiso).
2. ~~**Revocar los DOS tokens que pasaron por el chat**~~ → **HECHO**
   (el dueño los revocó al crear el nuevo, paso 1 de las instrucciones).
3. **§7.2 es dato, no código** (medido: el mecanismo está completo —
   403/401/200 verificado en vivo): teléfono en FASE1 (14.733 fichas
   sin teléfono, 100 % de las en revisión),
   `importar_municipio --todos` para los 16 municipios del padrón sin
   fichas, definir destacados y reparto de correctores (§11.4-k).
4. **Keystore de Android**: `keystore.properties` guarda la contraseña
   en texto claro (gitignorado, solo local). Si algún día se pierde el
   `.jks`, no se podrán firmar actualizaciones compatibles.

---

## Android: cabecera compacta (D-2026-10-29/13)

- **Queja del dueño** (viendo el APK): «el espacio para resultados es
  muy reducido en relación con la barra superior y la paginación» y
  «el selector de municipio y los filtros por categoría podrían estar
  en el mismo inline».
- **Decisión**: municipio + chips de categoría a **una sola fila**. La
  web no se toca (su `<label>Municipio</label>` + select siguen igual).
  En Android el selector pasa a **modo compacto**: sin etiqueta encima
  (eso es lo que ahorra alto) y con **tope de ancho de 160dp** para no
  comerse los chips. La etiqueta **no se pierde**: va en la descripción
  accesible («Municipio: Moca», TalkBack) y en el texto del selector
  cuando no hay municipio («Municipio»).
- **Ahorro medido en dp**: la tira de municipio+chips pasa de ~124dp
  (selector 72 + margen 12 + chips 40) a ~48dp → **−76dp**. Espaciado
  de cabecera 14/12/12/14 → 10/10/10/10 (−16dp) y contador de
  resultados 12+6 → 8+4 (−6dp). **Total ≈ −96dp** ≈ una fila más de
  tarjetas a la vista.
- **Paginación**: margen vertical 2dp → 0 (−4dp); las flechas se
  quedan en **40dp** por zona de toque (accesibilidad documentada en el
  propio código). **Suelo honesto**: la barra no puede bajar de ~40dp
  de contenido + el inset del sistema (16-24dp con gestos, 48dp con
  los 3 botones) sin romper accesibilidad; lo que de verdad le robaba
  alto a la rejilla era la cabecera de arriba.
- **Alternativa dejada sobre la mesa** (si al verlo sigue pareciendo
  mucho): subir la paginación a la línea del contador («38 resultados ·
  Página 1/5 ←→») y dejar el fondo libre (~+29dp más para la rejilla),
  a cambio de alejar las flechas del pulgar. No se hizo sin preguntar:
  cambia el patrón de uso.
- **Verificación**: `gradlew assembleRelease` → BUILD SUCCESSFUL,
  `lintVitalRelease` en verde, firma verificada con `apksigner`
  (mismo certificado) y **APK reexportado al escritorio**
  (`BuscandoAndo-v2026-10-29.apk`, se instala como actualización).
  Sin emulador local, el ajuste fino fino (p.ej. el tope de 160dp del
  selector en pantallas muy estrechas) queda para la revisión del
  dueño en su teléfono.
