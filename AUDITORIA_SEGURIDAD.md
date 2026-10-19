# Auditoría de seguridad — 19 de octubre de 2026

## Qué se revisó y cómo

Auditoría dirigida del sistema completo, con peticiones de **solo lectura**
contra producción y revisión de código y del repositorio:

* **Backend Django**: `settings.py`, permisos de todos los endpoints de la
  API, la herramienta de levantamiento (§11.5) y su token, importar/exportar
  JSON del admin, health check.
* **Frontend React**: buscador de XSS peligroso (`dangerouslySetInnerHTML`,
  `eval`), claves incrustadas, orígenes externos.
* **APK Android**: manifiesto (permisos, exportados, backups, tráfico en
  claro) y certificado de firmas.
* **Repositorio e historial de git**: ficheros trackeados y todo el historial
  (búsqueda por contenido, `-S`) de la contraseña del keystore, la del admin,
  el token de colaborador y la contraseña de la BD local.
* **Producción en vivo** (`buscandoando.onrender.com`): cabeceras HTTP,
  cookies, CORS, redirección http→https, fuga de ficheros sensibles,
  traversal de directorios y respuesta a Hosts ajenos.

Lo que NO se hizo (por si se quiere ampliar): no se ejecutó fuerza bruta
real sobre el login, no se corrieron escáneres automáticos (nuclei, etc.) ni
se auditaron servicios de terceros (Render, Cloudinary, Cloudflare).

---

## Resumen de hallazgos

| # | Hallazgo | Severidad | Estado |
|---|----------|-----------|--------|
| 1 | Lectura arbitraria de ficheros del servidor en la vista SPA | **Crítica** | Corregido (commit `33996dd`) |
| 2 | La IP del `Envio` se podía falsificar | Media | Corregido |
| 3 | Sin HSTS ni CSP; cookies de sesión/CSRF sin `Secure` | Media | Corregido |
| 4 | APK con `android:allowBackup="true"` | Baja | Corregido (surtirá en el próximo build) |
| 5 | Sin límite de intentos en `/admin/login/` | Media | **Corregido** (freno en la app) |
| 6 | Confirmar `SECRET_KEY` en el panel de Render | Media | **Verificado** (existe, valor aleatorio) |
| 7 | Keystore de firmas dentro de la carpeta sincronizada con OneDrive | Media | **Recomendación** |
| 8 | Varios menores (ver §8) | Baja/Info | Documentados |

---

## 1. CRÍTICO — La vista SPA abría ficheros del servidor (corregido)

### Qué pasaba

`serve_react` (`backend/views.py`), la vista que sirve el build de React y
hace de fallback para las rutas del SPA, construía la ruta así:

```python
file_path = build_dir / path          # path viene de la URL
if file_path.exists() and file_path.is_file():
    return FileResponse(open(file_path, 'rb'), ...)
```

`pathlib` une segmentos absolutos **reemplazando** la base. Con una petición
cuyo path empieza por `//`, la vista terminaba abriendo un fichero absoluto
del servidor. Comprobado en producción (solo lectura):

* `GET //etc/passwd` → **200** con el fichero real (`root:x:0:0:root:...`).
* `GET //etc/os-release` → **200** con el SO del contenedor (Debian 12).
* `GET //opt/render/project/src/render.yaml` → **200** con el fichero entero
  (2.304 bytes): el `render.yaml` del repositorio desplegado era legible, y
  con la misma ruta todo el código fuente del despliegue.
* `GET //proc/self/environ` → 200 pero **vacío**: `/proc` devuelve tamaño 0
  y la respuesta salía con `Content-Length: 0`. Los secretos de entorno
  (SECRET_KEY, DATABASE_URL, etc.) **no se filtraron, pero por casualidad**,
  no por diseño: no se puede dar por bueno.

Las variantes con `..` (`/../../proc/self/environ`) las bloqueaba el borde
de Cloudflare antes de llegar a Django; la variante `//` pasaba sin más.

### Impacto

Cualquiera que llegue al dominio podía leer el código desplegado, ficheros
del sistema y cualquier archivo legible por el proceso (hoy no había secretos
en disco — todo va por variables de entorno —, pero basta un fichero con una
clave futuro para que fuera grave). Era la puerta más gorda del sistema.

### Corrección (commit `33996dd`)

En `backend/views.py` la ruta se aplana (`path.lstrip('/')`) y además se
exige que **resuelva dentro del build** antes de servirla:

```python
base = build_dir.resolve()
file_path = (build_dir / path.lstrip('/')).resolve()
if file_path.is_relative_to(base) and file_path.is_file():
    ...
```

Lo que no esté dentro del build cae al `index.html` del SPA, que es lo que
ya pasaba con las rutas normales. Hay **5 tests de regresión** en
`backend/config/tests.py` (clase `ServeReactSeguridadTests`) que fijan el
comportamiento con el ataque real (`//etc/passwd`), con `..` y con el
fallback de SPA.

---

## 2. MEDIA — La IP del `Envio` se podía falsificar (corregido)

`_ip()` leía la **primera** entrada de `X-Forwarded-For`. Esa cadena se
construye de izquierda a derecha: lo primero lo teclea **el cliente**, y cada
proxy anade el suyo al final. Quien mandaba un envío podía firmar la IP que
quisiera y el registro de auditoría (`Envio.ip`) salía falseado — que es
justamente lo que no puede hacer un registro de auditoría.

Corregido: ahora se lee la **última** entrada válida (la que declaró el
último proxy, que el cliente no puede reescribir); si no hay cadena, se usa
`REMOTE_ADDR`. El mismo día se completó la regla con la cabecera
**`CF-Connecting-IP`** por delante — solo Cloudflare puede escribirla y
trae al visitante de verdad, mientras que en la cadena `X-Forwarded-For` la
dirección del cliente queda en medio y al final acaba la del borde de
Cloudflare, común a todos. Añadidos 5 tests (`IPDelEnvioTests`). Recordatorio
del propio código: la IP es solo para mirar de dónde vienen los lotes;
**el bloqueo es por token, no por IP**.

---

## 3. MEDIA — Cabeceras y cookies de producción (corregido)

Lo que se observaba en producción y lo que falta ahora:

| Cabecera/cookie | Antes | Ahora |
|---|---|---|
| `Strict-Transport-Security` | ausente | `max-age=31536000` |
| `Content-Security-Policy` | ausente | política cerrada (abajo) |
| `X-Frame-Options` | `DENY` ✓ | `DENY` |
| `X-Content-Type-Options` | `nosniff` ✓ | `nosniff` |
| `Referrer-Policy` | `same-origin` ✓ | `same-origin` |
| Cookie `csrftoken` | **sin `Secure`** (verificado: `Path=/; SameSite=Lax`) | con `Secure` |
| Cookie de sesión | sin `Secure` | con `Secure` |

En `settings.py` (solo con `DEBUG=False`): `SECURE_HSTS_SECONDS = 31536000`,
`SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` (detrás de
Cloudflare/Render el https llega declarado en esa cabecera), y
`SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`. No se añade
`SECURE_SSL_REDIRECT`: Cloudflare ya redirige http→https (verificado: 301) y
duplicarlo solo añade riesgo de bucles.

La CSP la pone el middleware nuevo `config.middleware.CabecerasSeguridadMiddleware`:

* `script-src 'self'` — solo bundles propios (Vite y el admin de Django).
* `style-src 'self' 'unsafe-inline' https://unpkg.com` — React pinta
  atributos `style` en línea; unpkg es solo por el `leaflet.css` que enlaza
  el `index.html` (ver §8: conviene auto-alojarlo y cerrar esto a `'self'`).
* `img-src 'self' data: blob: https:` — fotos de Cloudinary y teselas del
  mapa.
* `connect-src 'self' https://res.cloudinary.com` — la API es del mismo
  origen.
* `object-src 'none'`, `frame-ancestors 'none'` (refuerza el clickjacking),
  `base-uri 'self'`, `form-action 'self'`.

---

## 4. BAJA — Backups del APK (corregido)

El manifiesto llevaba `android:allowBackup="true"` con las reglas de backup
**vacías** (las plantillas por defecto sin configurar). La app no guarda
datos privados (no usa tokens de colaborador: eso es de la herramienta web),
así que el riesgo era bajo, pero no cuesta nada cerrarlo: ahora
`android:allowBackup="false"`. **Surtirá en el próximo build del APK**; los
APKs ya repartidos quedan como están.

---

## 5. MEDIA (corregido el 19/oct) — Freno de intentos en el login del admin

No había **ningún** freno al intento de contraseña: ni django-axes, ni
throttling en el login, ni nada equivalente — un ataque de diccionario
contra `/admin/login/` podía probar sin límite.

Matiz descubierto al intentar la recomendación original: **el Cloudflare
que se ve delante del sitio (`Server: cloudflare`) es el de Render, no una
cuenta propia** — `buscandoando.onrender.com` vive en el dominio de Render
y no admite reglas nuestras desde ningún panel. Poner un rate limiting de
Cloudflare exigiría comprar un dominio propio (camino opcional, abajo), así
que el freno se metió en la aplicación:

**`config.middleware.ThrottleLoginAdmin`** — sin dependencias nuevas ni
tablas (los contadores viven en la cache del proceso; un reinicio los
borra, aceptable para un freno):

* **por IP**: 5 fallos → 10 minutos sin validar contraseñas;
* **por usuario**: 25 fallos → 15 minutos (un ataque que cambie de IP a
  cada rista acaba en el techo de usuario; un escaner aleatorio no alcanza
  25 veces el mismo usuario y no candade la cuenta a posta);
* cuando salta, responde **429 + `Retry-After` sin comprobar la
  contraseña** — el diccionario no gana nada probando contra el hash;
* un login bueno **borra** sus contadores; el formulario (GET) nunca se
  freña; los intentos que llegan con el freno puesto **no alargan** la
  espera (nadie puede condenar la cuenta a candado permanente).

La IP del contador usa la misma regla que los `Envio`, ahora con la
cabecera **`CF-Connecting-IP`** por delante: solo Cloudflare puede
escribirla y trae al visitante de verdad, que en la cadena
`X-Forwarded-For` queda en medio (el cliente puede anteponer lo que quiera
y al final acaba la dirección del borde de Cloudflare, que es la misma para
todos). Respaldo: última entrada válida de la cadena, y `REMOTE_ADDR`.

7 tests nuevos (los 5 caminos del freno + 2 de la cabecera nueva). Camino
opcional futuro, si algún día hay dominio propio: la regla de Cloudflare
describa en el camino B de los apuntes (5 cada 10 minutos por IP sobre
`/admin/login/`) — con las dos capas a la vez no se estorban.

---

## 6. MEDIA (verificado el 19/oct) — `SECRET_KEY` en el panel de Render

`settings.py` usa `SECRET_KEY` del entorno con un valor por defecto
**público** (`django-insecure-cambiar-en-produccion`) si nadie la define. El
`render.yaml` la genera (`generateValue: true`), **pero el propio archivo
avisa de que el servicio `buscandoando` se dio de alta desde el panel, no
desde un Blueprint, y que ese archivo no gobierna lo desplegado** — así que
la única forma de saberlo era mirar el panel.

**Resolución**: el dueño comprobó el 19/oct de 2026 en Render → servicio
`buscandoando` → *Environment* que `SECRET_KEY` **existe con un valor
aleatorio**. Producción firma con clave propia: sin acción pendiente. Único
consejo: guardar una copia de esa variable en un lugar seguro (gestor de
contraseñas o cuaderno), porque es la llave maestra del sitio.

---

## 7. MEDIA (recomendación) — El keystore de firmas

`android/keystore/buscandoando-release.jks` vive dentro de la carpeta del
proyecto, que está sincronizada con **OneDrive**, y su contraseña se ha
compartido por chat. Juntos (archivo + contraseña), permitirían a quien los
consiga firmar "actualizaciones oficiales" de la app, que los teléfonos que
la tienen instalada aceptarían sin advertir. Hoy el `.jks` **no está en git
ni en el historial** (verificado con `git ls-files` y búsqueda por contenido
en todo el historial) y `android/.gitignore` ya lo excluye correctamente —
el riesgo es del copiado en la nube, no del repo.

**Recomendación**: copia del `.jks` en un disco externo (fuera de OneDrive),
y considerar cambiar la contraseña del keystore
(`keytool -storepasswd -keystore buscandoando-release.jks`; el archivo no
cambia, solo la clave). Repartir la nueva contraseña por un canal distinto
al chat.

---

## 8. Hallazgos menores (documentados, sin corregir)

* **`.onrender.com` como comodín en `ALLOWED_HOSTS`** (render.yaml): acepta
  cualquier subdominio de onrender.com. Conviendría restringir a
  `buscandoando.onrender.com` (y los previews de PR si se usan). Impacto
  bajo: no hay flujos de correo ni de restablecimiento de contraseña que
  exploten el Host.
* **Sin techo de peticiones en `GET /api/pendientes/`** (requiere token
  válido o sesión de admin; es solo lectura del reporte) **ni en
  `POST /api/corrections/`** (público a propósito: el riesgo es spam en la
  cola de revisión, no compromiso). El endpoint de envío del colaborador
  **sí** tiene techo: 30/min por token.
* **`requirements.txt` sin fijar versiones** (rangos `>=`): para
  reproducibilidad y para poder vigilar CVEs con calma convendría un lock o
  versiones exactas. Hoy la instalación trae Django 5.2.18, el parche
  actual de la rama 5.2.
* **`backend/export_data.py`** (no trackeado) contiene la contraseña de la
  BD local de desarrollo. No está en git ni en el historial, pero es un
  recordatorio de no dejar contraseñas ni siquiera en ficheros locales.
* **`GET /api/health/` expone el SHA del commit**: es a propósito (saber qué
  código hay en producción), solo informativo.
* **El token de colaborador vive en `localStorage`** de la herramienta web:
  con la CSP actual un XSS no podría usarlo desde otro origen, pero
  recordar que es una *firma, no una sesión* (§11.5): se puede apagar el
  token y ya.

---

## Verificado limpio

* **Nada sensible en git**: keystore (`.jks`), `keystore.properties` y
  `.env` no están trackeados ni aparecen nunca en el historial
  (`git ls-files` + búsqueda por contenido en todos los commits de la
  contraseña del keystore, la del admin, el token de colaborador y la de la
  BD local: 0 resultados).
* **Token de colaborador**: generado con `secrets.token_urlsafe(32)` (256
  bits de entropía criptográfica), viaja **solo en cabecera** (nunca en la
  URL), se compara por consulta exacta en la BD y el bloqueo es por token
  (`activo=False`), sin tocar a los demás.
* **Permisos de la API**: negocios en lectura pública (`ReadOnlyModelViewSet`);
  correcciones creables por cualquiera (a propósito, con revisión manual);
  importar/exportar JSON **solo staff** (comprobado en código y con sesión);
  admin de Django tras login.
* **`DEBUG=False` en producción** (verificado: 404 genérico, sin páginas de
  depuración ni volcado de ajustes).
* **CORS**: el origen ajeno no recibe `Access-Control-Allow-Origin` (ni
  `*`); solo se refleja el propio.
* **http:// → 301 https://** (Cloudflare). **Host ajeno → 403.**
* **Frontend**: sin `dangerouslySetInnerHTML`, `eval` ni claves
  incrustadas; el token se teclea en un campo `type="password"`.
* **Android**: sin tráfico en claro (todo https), sin claves incrustadas,
  `exported="true"` solo en la actividad lanzadora.
* **Servidor al día**: Django 5.2.18 (parche actual de la rama 5.2 LTS).

---

## Verificación en producción (tras el deploy del commit `33996dd`)

El despliegue se confirmó por el propio health check (`"commit":
"33996dd17009ecc9752b9f255a872f296bc7fef2"`) y se repitió la batería de
sondeos, con este resultado:

* **Traversal cerrado**: `//etc/passwd`, `//proc/self/environ` y
  `//opt/render/project/src/.git/config` devuelven ahora el `index.html`
  del SPA; las variantes con `..` siguen cayendo en el 400 del borde. El
  fichero del servidor ya no se alcanza por ninguna de las rutas probadas.
* **Cabeceras nuevas presentes**: `Strict-Transport-Security:
  max-age=31536000` y la `Content-Security-Policy` completa.
* **Cookies con `Secure`**: en `/admin/login/` la cookie `csrftoken` sale
  ahora con `Secure` (antes salía solo `Path=/; SameSite=Lax`).
* **Ronda visual** (navegador, con consola abierta): portada (React pinta,
  6 imágenes sin roturas), ficha de negocio con mapa Leaflet (12 teselas
  sin roturas, © OpenStreetMap/Esri), admin logueado (índice completo) y
  `/levantamiento` (campo de token). **Cero mensajes de consola y cero
  violaciones de CSP** en las cuatro páginas: la política cerrada no rompe
  nada de lo que se usa a diario.
* El resto seguía igual de limpio: CORS sin reflejar orígenes ajenos,
  http→https con 301, Host ajeno con 403, 404 genérico sin fuga de
  DEBUG.

Único cambio posterior al informe: el build del APK obligó a recolocar un
comentario del manifiesto (XML no admite comentarios dentro de una
etiqueta); se corrigió antes de generar los APK nuevos.

---

## Estado de la suite

209 tests del backend en verde tras los cambios: los del health check, los
de la vista SPA (5), los de la IP (5), los del freno de login (7) y toda
la suite previa.
