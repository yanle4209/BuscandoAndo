# Desplegar BuscandoAndo en otra máquina con Coolify

Guía de la exportación: qué se añadió al proyecto, cómo se construye la
imagen, cómo se instala en Coolify y cómo se traen los datos de producción.

Todo lo que hay aquí está probado contra el código actual (commit
`ca42941`), con Django 5.2.18 y Python 3.14.

---

## 1. Qué se añadió al proyecto

| Archivo | Para qué |
|---|---|
| `Dockerfile` | Imagen única: compila React en una etapa Node y sirve todo con Django + Gunicorn en una etapa Python. |
| `docker/entrypoint.sh` | Espera la BD, migra, recoge estáticos, crea el admin, carga datos iniciales y arranca Gunicorn. |
| `docker-compose.yaml` | Servicio `app` + Postgres 17 + volúmenes. Es lo que Coolify detecta. |
| `.dockerignore` | Deja fuera `.venv`, `node_modules`, `.env`, `media`, `db.sqlite3`, logs y la app Android. |
| `.env.coolify.example` | Plantilla de variables, comentada, sin secretos. |
| `deploy/docker-compose.local.yaml` | Abre el puerto 8000 solo en local para probar desde el navegador. Coolify no lo usa. |
| `deploy/empaquetar.sh` | Genera un `.tar.gz` limpio para llevar el proyecto a otra máquina. |
| `COOLIFY.md` | Este documento. |

También se añadió una variable opcional `CSRF_TRUSTED_ORIGINS` en
`backend/config/settings.py` (vacía por defecto, no cambia nada en
Render). Sirve para que el login del admin funcione cuando se prueba
por IP o por un dominio que el contenedor no conoce.

---

## 2. Cómo queda la arquitectura

```
Internet
   |
Traefik (Coolify)  -- TLS Let's Encrypt
   |
   +--> app  (Django + Gunicorn, puerto 8000)
   |      |- /            -> SPA compilada (frontend/dist)
   |      |- /api/...     -> DRF
   |      |- /admin/      -> panel
   |      |- /static/...  -> WhiteNoise
   |      `- /media/...   -> volumen media_data (solo sin Cloudinary)
   |
   `--> db   (postgres:17-alpine, red interna, sin puerto publicado)
```

Una sola imagen, un solo contenedor de aplicación. No hace falta Nginx:
`views.serve_react` ya sirve el SPA y WhiteNoise los estáticos.

El `docker-compose.yaml` **no publica** el 8000 al host (usa `expose`),
así no choca con nada que ya escuche ahí. Traefik entra por la red
interna del compose.

---

## 3. Requisitos en la máquina destino

- Docker 24 o superior y el plugin `docker compose` v2.
- Coolify v4 instalado y funcionando (con Traefik y su red).
- 1 GB de RAM libre como mínimo. La imagen ronda los 500 MB y el
  proceso necesita ~300 MB en marcha.
- Un dominio o subdominio apuntando a la IP del servidor (registro A),
  si se quiere HTTPS. Sin dominio se puede probar por IP, pero con
  matices (ver sección 12).

---

## 4. Opción A — desplegar desde Git (recomendada)

Es la que permite redesplegar con un `git push`.

1. Sube el repo a GitHub/GitLab (ya está en
   `https://github.com/yanle4209/BuscandoAndo.git`) con estos archivos
   nuevos incluidos:

   ```bash
   git add Dockerfile docker-compose.yaml .dockerignore \
           .env.coolify.example COOLIFY.md docker/entrypoint.sh \
           deploy/empaquetar.sh backend/config/settings.py
   git commit -m "chore: despliegue con Docker y Coolify"
   git push origin main
   ```

2. En Coolify: **+ New** → **Resource** → **Application**.

3. **Source**: elige el repositorio. Si es privado, conéctalo por
   GitHub App; si es público, basta la URL.

4. **Build Pack**: `Docker Compose`.

5. Ajustes de build:
   - **Base Directory**: `/`
   - **Docker Compose Location**: `/docker-compose.yaml`

6. **Domains**: escribe `https://tudominio.com` y guarda. Coolify crea
   la ruta en Traefik y pide el certificado. El puerto que usa es el
   `8000` que declara el `expose` del compose; no hay que tocarlo.

7. Pestaña **Environment Variables**: copia el contenido de
   `.env.coolify.example` y rellena al menos:
   - `SECRET_KEY` (genera una nueva, ver abajo)
   - `POSTGRES_PASSWORD`
   - `ALLOWED_HOSTS`
   - `SITIO_URL`
   - `CSRF_TRUSTED_ORIGINS`
   - `DJANGO_SUPERUSER_PASSWORD`

   En Coolify el botón **Developer view** permite pegar el bloque entero
   de una vez.

8. **Deploy**. El primer build tarda unos minutos (instala dependencias
   de Python, compila Vite y arranca Postgres).

9. Mira los logs del servicio `app` hasta ver:

   ```
   == migrate ==
   == collectstatic ==
   == setup_admin ==
   == gunicorn en 0.0.0.0:8000 ==
   ```

---

## 5. Variables de entorno

### Obligatorias

| Variable | Ejemplo | Nota |
|---|---|---|
| `SECRET_KEY` | `...` | Nunca reutilizar la de producción. Generar nueva. |
| `POSTGRES_PASSWORD` | `...` | Solo para la BD interna del compose. |
| `ALLOWED_HOSTS` | `buscandoando.app,www.buscandoando.app` | Sin esquema ni barras. |
| `SITIO_URL` | `https://buscandoando.app` | Canonical, og:url y sitemap. |
| `DJANGO_SUPERUSER_PASSWORD` | `...` | Sin ella, `setup_admin` no crea nada. |

Generar la clave:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Recomendadas

| Variable | Valor | Por qué |
|---|---|---|
| `DEBUG` | `False` | Activa HSTS, cookies Secure y CSP. |
| `CSRF_TRUSTED_ORIGINS` | `https://tudominio.com,https://www.tudominio.com` | Evita «CSRF verification failed» al entrar al admin. |
| `CORS_ALLOWED_ORIGINS` | `https://tudominio.com` | Solo necesario si algo externo llama a la API. |
| `WEB_CONCURRENCY` / `WEB_THREADS` | `2` / `4` | 8 peticiones simultáneas, igual que Render. |
| `ESPERAR_BD` | `1` | Espera a Postgres antes de migrar. |
| `CARGAR_FICHAS` | `0` (o `1` una vez) | Carga las ~1.800 fichas nacionales. |

### Fase geográfica

`FASE1_PROVINCIAS=Espaillat` y `FASE1_MUNICIPIOS=Moca` vienen por
defecto: en una instalación nueva **solo se verá Moca**. Para abrir todo
el país, deja las dos variables vacías.

---

## 6. Opción B — desplegar sin Git, con el paquete

Útil si la máquina destino no tiene acceso al repositorio.

En la máquina de origen:

```bash
cd /home/yanle/workspace/BuscandoAndo
./deploy/empaquetar.sh
```

Genera `../buscandoando-deploy-AAAAMMDD.tar.gz` (unos pocos MB: el
código, las fichas nacionales y los archivos de despliegue; sin `.venv`,
`node_modules`, `.git` ni fotos).

En la máquina destino:

```bash
mkdir -p /opt/buscandoando && cd /opt/buscandoando
tar -xzf buscandoando-deploy-AAAAMMDD.tar.gz
cp .env.coolify.example .env
nano .env                      # SECRET_KEY, POSTGRES_PASSWORD, dominio
docker compose up -d --build
```

Si además se quiere gobernar desde Coolify, hay dos caminos:

- subir ese mismo contenido a un repo Git y usar la Opción A, o
- en Coolify, **+ New** → **Resource** → **Docker Compose Empty** y
  pegar el contenido de `docker-compose.yaml`, dejando que Coolify
  construya desde un repositorio (el compose necesita el `build` con el
  código, así que el repo sigue siendo lo natural).

---

## 7. Base de datos: interna o externa

### Por defecto: Postgres del compose

No hay que configurar nada más que `POSTGRES_PASSWORD`. El contenedor
`db` guarda los datos en el volumen `pg_data` y solo es alcanzable desde
la red interna.

### Con una base gestionada por Coolify o Neon

1. Crea el recurso PostgreSQL en Coolify (o usa el `DATABASE_URL` de
   Neon).
2. Define `DATABASE_URL` en las variables de `app`.
3. **Borra** del `docker-compose.yaml` el servicio `db`, el volumen
   `pg_data` y el bloque `depends_on`.

Con `DATABASE_URL` definida, el compose no usa la URL interna.

---

## 8. Traer los datos de producción (Neon)

El sitio actual tiene las fichas en Neon. Sin este paso, la instalación
nueva arranca con el fixture (`load_initial_data`) y las fichas
nacionales si se activa `CARGAR_FICHAS`.

### 8.1 Volcar desde Neon

En una máquina con `pg_dump` 17 y acceso a la base:

```bash
pg_dump --no-owner --no-acl -Fc "$DATABASE_URL_NEON" > buscandoando.dump
```

`-Fc` es el formato comprimido de `pg_restore`; conserva secuencias y
permite restaurar por tablas si algo falla.

### 8.2 Copiar al servidor

```bash
scp buscandoando.dump usuario@servidor:/opt/buscandoando/
```

### 8.3 Restaurar

Con la aplicación parada para que nadie escriba mientras se restaura:

```bash
cd /opt/buscandoando
docker compose stop app
docker compose up -d db

docker compose exec -T db pg_restore \
  -U buscandoando -d buscandoando \
  --clean --if-exists --no-owner --no-acl \
  < buscandoando.dump

docker compose up -d
```

Al arrancar, el entrypoint vuelve a correr `migrate` (por si el dump es
de una versión anterior del esquema), `collectstatic` y `load_initial_data`
(que se salta todo porque ya hay datos).

Comprobar:

```bash
docker compose exec -T db psql -U buscandoando -d buscandoando \
  -c "select count(*) from businesses_business;"
```

---

## 9. Fichas nacionales

El archivo `backend/data/fichas_nacionales.ndjson.gz` (441 KB) viaja en
el repo y en el paquete. Cargarlo es opcional y **no** debe hacerse en
cada arranque: son ~1.800 filas y en Render provocó el incidente del
20/oct por lanzarlo durante el build (DISENO.md 15.5).

Una sola vez:

```bash
docker compose exec app python manage.py cargar_fichas \
  data/fichas_nacionales.ndjson.gz
```

Es idempotente y reanudable: repetirlo no duplica nada.

Si ya se restauró el dump de Neon, **no hace falta**: esas fichas ya
vienen dentro.

---

## 10. Medios (fotos)

### Con Cloudinary (como producción)

Rellena `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` y
`CLOUDINARY_API_SECRET`. Las imágenes se sirven desde
`res.cloudinary.com` y el volumen `media_data` queda sin uso. La CSP ya
permite ese dominio (`config/middleware.py`).

### Sin Cloudinary

Sin credenciales, `STORAGES` cae a `FileSystemStorage` y las fotos van a
`/app/backend/media`, que es el volumen `media_data`. Django las sirve en
`/media/` (la ruta se registra en `config/urls.py` solo en ese caso).

Para llevar las fotos locales existentes (26 MB, no van en el paquete):

```bash
docker cp ./backend/media/. "$(docker compose ps -q app):/app/backend/media/"
```

---

## 11. Operación

### Ver logs

```bash
docker compose logs -f app
docker compose logs -f db
```

### Actualizar el código

Con Git y Coolify: `git push` y botón **Redeploy** (o webhook
automático). Manual:

```bash
git pull
docker compose up -d --build
```

### Copia de seguridad

```bash
docker compose exec -T db pg_dump -U buscandoando -d buscandoando -Fc \
  > backup-$(date +%F).dump
```

Restaurar es el mismo `pg_restore` de la sección 8.3.

### Comandos puntuales

```bash
docker compose exec app python manage.py shell
docker compose exec app python manage.py createsuperuser
docker compose exec app python manage.py migrate
```

### Health check

```bash
curl -s http://127.0.0.1:8000/api/health/   # desde el host no se publica
docker compose exec app curl -s http://127.0.0.1:8000/api/health/
```

Devuelve `status: ok` y el estado de la BD en el campo `db`. Responde
200 aunque la BD falle a propósito: mide el proceso, no los datos.

---

## 12. Avisos importantes

### HTTPS no es opcional con `DEBUG=False`

Con `DEBUG=False` el proyecto activa `SESSION_COOKIE_SECURE` y
`CSRF_COOKIE_SECURE`. Si se prueba por `http://IP:8000`, el navegador no
enviará la cookie de sesión y el admin entrará en un bucle de login sin
explicación. Para pruebas por HTTP, arranca con `DEBUG=True` y sin HSTS,
o usa el dominio con HTTPS de Coolify.

Ojo también con HSTS: una vez que un navegador ve el dominio con HSTS,
fuerza HTTPS durante un año. No lo actives en un dominio de pruebas que
luego quieras usar por HTTP.

### `ALLOWED_HOSTS` con el dominio real

Si ves `DisallowedHost` en los logs, la variable no incluye el dominio
con el que estás entrando (sin esquema, sin puerto).

### El puerto tiene que ser 8000

El `expose` del compose y el `--bind` de Gunicorn están alineados en
8000. Si cambias `PORT`, cambia también el `expose` y el health check.

### Los workers

`2 workers × 4 hilos` es lo que se midió en Render. En una máquina con
menos de 1 GB, baja a `WEB_CONCURRENCY=1` y `WEB_THREADS=4`.

---

## 13. Probar en local antes de subir

Con Docker instalado en la máquina de origen:

```bash
cd /home/yanle/workspace/BuscandoAndo
cp .env.coolify.example .env
# rellenar SECRET_KEY y POSTGRES_PASSWORD; para local, DEBUG=True
docker compose -f docker-compose.yaml -f deploy/docker-compose.local.yaml up -d --build
docker compose logs -f app
```

El compose principal no publica el puerto (en Coolify entra Traefik), así
que el fichero `deploy/docker-compose.local.yaml` es el que abre el 8000
en `127.0.0.1`. Luego abrir `http://localhost:8000`.

Para probar el panel, pon `DEBUG=True` en el `.env`: con `DEBUG=False` las
cookies son `Secure`, el navegador no las manda por HTTP y el login del
admin entra en bucle.

Parar y borrar todo (incluida la BD):

```bash
docker compose -f docker-compose.yaml -f deploy/docker-compose.local.yaml down -v
```

---

## 14. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| 502 Bad Gateway | El contenedor no arrancó o no escucha en 8000 | `docker compose logs app`; revisar `PORT` y el `expose`. |
| `DisallowedHost` | Falta el dominio en `ALLOWED_HOSTS` | Añadirlo sin esquema ni puerto. |
| Bucle de login en `/admin/` | Cookies Secure sobre HTTP, o CSRF | Usar HTTPS, o `DEBUG=True` en pruebas; definir `CSRF_TRUSTED_ORIGINS`. |
| `CSRF verification failed` | Origen no confiado | Añadir el dominio a `CSRF_TRUSTED_ORIGINS`. |
| 500 en todo lo que usa datos | `DATABASE_URL` mal o Postgres caído | `docker compose logs db`; probar `docker compose exec app python manage.py check --database default`. |
| Estáticos 404 | `collectstatic` no corrió o `STATIC_ROOT` cambió | `docker compose exec app python manage.py collectstatic --noinput`. |
| Imágenes 500 en el admin | Sin credenciales de Cloudinary y sin volumen | Definir Cloudinary o montar `media_data`. |
| `pg_restore: error: ... already exists` | Restaurar sin `--clean` | Añadir `--clean --if-exists`. |
| El arranque tarda mucho | `CARGAR_FICHAS=1` | Volver a `0` después de la primera carga. |

---

## 15. Checklist de puesta en marcha

- [ ] Repo con `Dockerfile`, `docker-compose.yaml`, `docker/entrypoint.sh`.
- [ ] `SECRET_KEY` nueva y guardada en el gestor de secretos.
- [ ] `POSTGRES_PASSWORD` fuerte.
- [ ] `ALLOWED_HOSTS` y `SITIO_URL` con el dominio definitivo.
- [ ] `CSRF_TRUSTED_ORIGINS` con `https://` y `https://www.`.
- [ ] Dominio apuntando al servidor y certificado emitido.
- [ ] Deploy verde y `/api/health/` con `db: ok`.
- [ ] `/admin/` entra y se puede crear/editar una ficha.
- [ ] Una ficha pública carga con foto.
- [ ] `/sitemap.xml` y `/robots.txt` responden 200.
- [ ] `CARGAR_FICHAS=0` tras la primera carga.
- [ ] Copia de seguridad programada (`pg_dump` diario).
