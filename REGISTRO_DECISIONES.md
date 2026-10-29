# Registro de decisiones — sesión de revisión y finalización

> Registro de las decisiones tomadas durante la revisión asistida
> (inicio: 28–29/oct 2026), para que el dueño pueda consultarlas y
> revertirlas. Cada entrada dice **qué**, **por qué** y **cómo
> deshacerlo**. Orden cronológico inverso (lo último, arriba).

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
  abiertos como posible tarea futura.
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
