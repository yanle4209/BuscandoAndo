# BuscandoAndo 🔍

Plataforma de búsqueda de servicios y negocios de República Dominicana.
Backend Django + DRF, frontend React (Vite) y app Android nativa, que leen
todos la misma API.

**En producción**: https://buscandoando.onrender.com (Render + Neon
PostgreSQL + Cloudinary). Visible en FASE1 — provincias Espaillat,
Santiago, La Vega y Hermanas Mirabal (ver `DISENO.md` §13).

## Cómo funciona (las tres reglas)

- La búsqueda es **a 5 km** del punto activo: el GPS si está disponible;
  si no, la cabecera municipal que elija el usuario (R1/R3).
- Crear una ficha a mano → queda **En Revisión** → solo el admin publica
  (`VISION.md`). Lo importado que cumple el trío *nombre + teléfono +
  punto* se publica solo y lo demás queda marcado como pendiente
  (`DISENO.md` §10).

## Estructura del repositorio

```
BuscandoAndo/
├── backend/          # Django + DRF (config + 11 apps)
├── frontend/         # React 19 + Vite (los mismos endpoints)
├── android/          # App Android (Kotlin)
└── *.md              # Documentación de diseño y auditorías
```

## Backend (Django + DRF)

### Apps

| App | Qué |
|---|---|
| `config` | Settings, middleware (CSP, frenos de login/correcciones), health check |
| `businesses` | Negocios, correcciones, colaboradores, envíos de campo, comandos de importación |
| `categories` | Categorías (con jerarquía padre/hijo) |
| `business_locations` / `business_contacts` / `business_hours` / `business_images` | Dirección, contacto, horario e imágenes (OneToOne/FK por negocio) |
| `publication_status` / `operational_status` | Catálogos de estado |
| `uso` | Métricas de uso (búsquedas, términos, avisos de interés) |
| `seo` | Metas por ruta y robots.txt editables desde el panel |

### Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/health/` | Health check (no toca la BD; expone el commit desplegado) |
| GET | `/api/businesses/` | Listar negocios (solo publicados, recortados a FASE1) |
| GET | `/api/businesses/<slug>/` | Detalle de negocio |
| GET | `/api/businesses/featured-by-search/` | Destacados dentro del círculo de la búsqueda |
| GET | `/api/categories/` | Listar categorías |
| GET | `/api/cabeceras/` | Cabeceras municipales de las provincias de fase |
| GET/POST | `/api/corrections/` | Reportar un error en una ficha (POST público, con revisión manual) |
| POST | `/api/interes/` | Aviso «quiero que lleguen aquí» (solo métrica agregada) |
| GET | `/api/pendientes/` | Reporte de fichas incompletas por municipio (solo staff) |
| POST | `/api/levantamiento/` | Envío de campo con token de colaborador (sin login) |
| — | `/admin/` | Panel de administración (gestión, SEO, reportes) |

### Filtros de búsqueda (en `/api/businesses/`)

- `?text=restaurante` — nombre, descripción o categoría (alias `?search=`)
- `?category=restaurantes` — filtrar por categoría
- `?lat=19.40&lng=-70.53&radius=5` — círculo desde el punto activo
  (`radius` se recorta a **5**: pedir 10 devuelve lo mismo que pedir 5)
- `?featured=true` — solo destacados

> `?city=` **no es filtro**: la ciudad son coordenadas + 5 km (R3.5).

### Instalación

```bash
cd backend
python -m venv venv
venv\Scripts\activate         # Windows (en Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py load_initial_data   # categorías y estados base
python manage.py setup_admin         # crea el admin (ver abajo)
python manage.py runserver
```

El superusuario se crea con `setup_admin` a partir de variables de
entorno (`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`,
`DJANGO_SUPERUSER_EMAIL`); **si falta la contraseña, no crea nada y lo
dice**. En Render la genera el propio servicio (`generateValue: true`).

### Comandos de datos

| Comando | Qué hace |
|---|---|
| `importar_municipio --todos` | Importa candidatos de OpenStreetMap por municipio (idempotente) |
| `exportar_fichas [salida]` | Exporta el padrón a JSONL gz (`backend/data/`) |
| `cargar_fichas <archivo>` | Carga un padrón en destino (idempotente y reanudable) |

## Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev      # desarrollo en :5173 (proxy /api → backend en :8000)
npm run lint     # oxlint
npm run build    # build de producción → dist/ (lo sirve Django)
```

En desarrollo, levanta el backend en `:8000` y el proxy de Vite se
encarga del resto. En producción, Django sirve `frontend/dist` con
metas SEO pintadas en el servidor y 404 real para rutas inexistentes.

## Android (Kotlin)

App nativa en `android/` con los mismos endpoints. Los tests unitarios
corren con `./gradlew testDebugUnitTest`.

## Despliegue y CI

- **Producción**: Render (web gratis) + Neon (PostgreSQL gratis). El
  build de Render compila el frontend y corre `migrate`,
  `setup_admin` y `load_initial_data`; `cargar_fichas` es manual (ver
  `DISENO.md` §15.5 y §16).
- **CI** (`.github/workflows/ci.yml`): en cada push/PR corren los tests
  de backend (SQLite en memoria, con el frontend buildeado como lo
  exige `serve_react`), el lint + build del frontend y los tests de
  Android.

## Documentación

| Archivo | Qué contiene |
|---|---|
| `DISENO.md` | Decisiones de diseño (R1–R6), geografía, fases, SEO, panel de admin |
| `VISION.md` | Visión del backend: tarjeta de resultado, estados, flujo de publicación |
| `AUDITORIA_SEGURIDAD.md` | Auditoría de seguridad (19/oct/2026) y sus correcciones |
| `MIGRACION_SERV00.md` | Plan opcional de migración a serv00.com |
