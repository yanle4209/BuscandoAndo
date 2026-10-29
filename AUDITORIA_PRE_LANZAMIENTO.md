# Auditoría pre-lanzamiento — BuscandoAndo
**URL:** https://buscandoando.onrender.com
**Fecha:** 19 oct 2026
**Método:** análisis por código/HTTP (HTML servido, bundle JS/CSS, API en vivo, headers). Sin revisión visual — ver "No verificado" al final.

---

## Resumen ejecutivo

La base técnica está **por encima de lo esperado en un proyecto asistido por IA**: headers de seguridad de nivel profesional, API bien construida y validada, sin secretos filtrados, buen rendimiento de primera carga. El **punto débil número uno es el SEO on-page**, que hoy es prácticamente inexistente para un directorio de negocios cuyo tráfico depende de Google. Nada que no se arregle en uno o dos días.

| Área | Nota |
|---|---|
| Seguridad | ★★★★★ |
| API / backend | ★★★★★ |
| Rendimiento | ★★★★☆ |
| SEO | ★☆☆☆☆ |
| Accesibilidad (estimada) | ★★☆☆☆ |
| Contenido / textos | ★★★☆☆ |

---

## Lo que está bien (no tocar)

**Seguridad — excepcional:**
- CSP estricta: `script-src 'self'` (sin inline, sin CDNs de scripts), `connect-src` limitado a `'self'` + Cloudinary, `frame-ancestors 'none'`, `object-src 'none'`.
- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, COOP.
- Sin claves ni tokens en el bundle (revisado: `VITE_*`, apikey, secret → 0 coincidencias).
- API solo same-origin: no devuelve cabeceras CORS con Origin externo (bien).
- Endpoints internos protegidos: `/api/pendientes/` → 403, `/api/levantamiento/` → 401 con token, `/api/corrections/` GET → 403.

**API (Django REST):**
- Validación correcta: `POST /api/corrections/ {}` → 400 con errores por campo en español (`"Este campo es requerido."`).
- Errores de paginación en JSON (`"Página inválida."`), no HTML.
- Respuestas rápidas: 0.2–0.5 s.
- Datos: 1839 negocios, 16 categorías, cabeceras geográficas de municipios.

**Rendimiento:**
- Primera carga: solo 5 peticiones (HTML + 1 JS + 2 CSS + favicon).
- JS: 525 KB bruto → **169 KB gzip, brotli activo**; CSS 55 KB.
- **Cero fuentes web** (font stack del sistema) — no hay bloqueo por tipografías.
- TTFB: 0.21–0.29 s. Assets con `Cache-Control: public, max-age=31536000, immutable` (hash en el nombre → perfecto).
- HTML con `no-cache` (los despliegues se ven al instante).
- Imágenes de negocios con `loading="lazy" decoding="async"`.

**Detalles bonitos detectados en el código:**
- Detector de nueva versión desplegada (polling del HTML + aviso "Nueva versión publicada").
- Estados de negocio calculados (abierto/cerrado/por horario con color).
- Rate-limit manejado en cliente ("Demasiados envíos").
- Correcciones de datos con formulario por campo — buena idea para un directorio.

---

## 🔴 Problemas altos (arreglar antes de lanzar)

### 1. SEO on-page casi inexistente
- **Sin `<meta name="description">`, sin Open Graph, sin Twitter Cards, sin `<link rel="canonical">`** en el HTML servido.
- **El título nunca cambia por ruta:** el bundle no contiene ni una sola asignación a `document.title` ni gestión de meta dinámica. Todas las páginas (home, ficha de negocio, levantamiento) se titulan igual: *"BuscandoAndo - Encuentra negocios en República Dominicana"*.
- **Impacto doble:** (a) las 1839 fichas de negocio no tienen señales únicas para Google; (b) al compartir en WhatsApp (y la app usa `wa.me`), **la preview saldrá sin imagen ni descripción** — en RD WhatsApp es el canal de compartir por excelencia.

**Fix:** `react-helmet-async` (o un `useEffect` que actualice title/meta) con título y descripción por ruta; para las fichas: `"Nombre – Categoría en Municipio, Provincia | BuscandoAndo"` + descripción con short_description. Idealmente prerenderizado (Vite SSR/`vite-plugin-ssg`) para que Google reciba el HTML listo.

### 2. `robots.txt` y `sitemap.xml` no existen de verdad
Ambos devuelven el **HTML de la SPA** (200, `content-type: text/html`). El rastreador no puede leer reglas ni sitemap, y no hay sitemap con los 1839 negocios.

**Fix:** crear `public/robots.txt` (`User-agent: *` + `Sitemap: https://buscandoando.onrender.com/sitemap.xml`) y generar `sitemap.xml` desde la API al construir (o endpoint dinámico). Los ficheros reales en `dist/` se sirven antes que el fallback de la SPA.

### 3. Soft-404: cualquier ruta devuelve 200
`/ruta-que-no-existe-xyz` → **200 text/html**. Google puede indexar páginas vacías/inexistentes.

**Fix:** en el servidor (Render), devolver 404 real para rutas que no existan y no sean fichas válidas, o al menos limitar el fallback a las rutas conocidas (`/`, `/business/*`, `/levantamiento`).

---

## 🟠 Problemas medios

### 4. Leaflet CSS cargado desde unpkg (render-blocking, sin SRI)
`index.html` incluye `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css` sin `integrity`, en el critical path. El JS de Leaflet **sí está empaquetado** — inconsistencia. unpkg es un tercero que puede caer o comprometerse.

**Fix:** importar `leaflet.css` desde `node_modules` (Vite lo empaqueta y con hash) y eliminar la etiqueta de unpkg.

### 5. Accesibilidad (estimada floja)
Recuento en el bundle:
- `alt:` en JSX: **3** — y 2 son de Leaflet. Las imágenes de negocios usan `alt: T.caption || ""` → **casi siempre alt vacío** (el campo caption no existe en la API).
- `sr-only`: **0** (sin utilidad de texto oculto para lector de pantalla).
- `aria-label`: 14 (varios del propio Leaflet) para toda una app con botones de icono y mapa.
- Sí hay `htmlFor` ×16 (bien) y `label`s asociados.

**Fix mínimo:** alt descriptivo automático (`"{name} – {category} en {municipio}"` cuando no hay caption), `aria-label` en todos los botones de icono, clase `sr-only` + skip-link, y pasar un Lighthouse/axe cuando tengáis navegador.

### 6. Textos sin acentos (visible para el usuario)
En el formulario de correcciones y footer:
- `"Contactanos"` → **Contáctanos** (aparece 2 veces)
- `"Descripcion"` → **Descripción**
- `"Categoria"` → **Categoría**
- `"Telefono / WhatsApp"` → **Teléfono / WhatsApp**
- `"Recibimos tu correccion sobre … El admin la revisara"` → **corrección … revisará**

### 7. Calidad de datos de lanzamiento
- Categorías sin acento: **"Clinicas" → "Clínicas"**, **"Educacion" → "Educación"**.
- Descripciones de categorías vacías (todas las visibles).
- Muchas fichas sin imágenes: en la página 3, **5 de 6 negocios con `images: []`**. Un directorio de negocios se juzga por sus fotos.

### 8. Un solo bundle de 525 KB (sin code-splitting)
0 `React.lazy`, 1 import dinámico. React + axios + Leaflet + toda la app viajan juntos en la primera carga. Con `React.lazy` por ruta y Leaflet cargado bajo demanda (home con mapa / ficha), bajarías el JS inicial a la mitad y mejorarías INP en gama baja — el público objetivo probablemente usa gama media/baja y datos móviles.

---

## 🟡 Menores

1. **Sin cabecera `Permissions-Policy`** (bloquear cámara/micrófono/geolocalización no necesarios; ojo, la geolocalización sí la usan — permitirla solo a `'self'`).
2. **HSTS** sin `includeSubDomains` ni `preload`.
3. **Sin `apple-touch-icon` ni manifest** — al añadir a inicio en iOS saldrá captura genérica.
4. **Plan Render:** si es el gratuito, la instancia duerme y el primer visitante espera ~40–60 s. El detector de versiones despierta el origen, pero no protege al primer usuario. Considerar uptime-cron o plan pago antes de anunciar.
5. Sin `preconnect`/`modulepreload` (menor: Chrome pre-carga módulos solo).

---

## ✅ Plan de acción sugerido (por orden)

1. **Meta por ruta** (title + description + OG) en las 3 rutas, con datos de la ficha en `/business/:slug`.
2. **`robots.txt` + `sitemap.xml`** generados desde la API (1839 URLs).
3. **Arreglar el 200 universal** de rutas inexistentes.
4. **Empaquetar Leaflet CSS** y quitar unpkg.
5. **Ronda de textos** (acentos) + datos (nombres de categorías, fotos de lanzamiento).
6. **Accesibilidad:** alt automáticos, aria-label en botones de icono, skip-link.
7. **Code-splitting** de rutas y Leaflet.
8. Reejecutar Lighthouse + axe con navegador cuando la web esté en fases finales.

---

## No verificado (limitaciones de esta auditoría)

Por un problema del navegador en este entorno (no de la web), no pude verificar **lo visual**:
- Diseño, espaciados, tipografía, contraste de colores.
- Comportamiento responsive real (móvil/tablet) y tamaños táctiles.
- Formularios y mapa **en ejecución** (la lógica está revisada en código, no clicada).
- Core Web Vitals reales (LCP/CLS/INP) y prueba con Lighthouse.

Si me pasas capturas (escritorio y móvil, home y ficha de negocio), completo la revisión visual sobre ellas.
