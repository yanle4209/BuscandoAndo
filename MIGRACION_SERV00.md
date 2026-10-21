# Migración a serv00.com — fase beta sin dinero

> Contexto (21/oct/2026): Render **caducó la base de datos gratis** (las BD
> gratis de Render viven 30 días; la nuestra cumplió 30 el 21/oct). Mientras
> estuvo caída dio síntomas engañosos: el build falló en `migrate` con
> «could not translate host name», y TODA ruta con BD devolvía 500. El import
> `cargar_fichas` que corría en el build (ya eliminado, DISENO.md 15.5) fue
> coincidencia, no causa. Upgrade de pago = 6 $/mes; no hay dinero para la
> beta, así que migramos a **serv00.com** (gratis, sin tarjeta, sin caducidad
> de BD). Este documento es el plan completo y la memoria de ejecución.

## 1. Qué se pierde y qué se reconstruye

| Dato | Destino |
| --- | --- |
| 1.839 fichas publicadas | **Se reconstruye**: `backend/data/fichas_nacionales.ndjson.gz` (en git) + `cargar_fichas` (idempotente y reanudable) |
| Usuario admin y permisos | **Se reconstruye**: `manage.py setup_admin` |
| Metas SEO por ruta y robots.txt | **Se reconstruye solo**: la migración `seo/0002` resiembra los valores por defecto exactos |
| Reportes del Panel Levantamiento (`uso`) | ⚠️ **Se pierden** (solo existían en la BD de Render, inaccesible sin pago) |
| Ediciones manuales de fichas hechas en el admin | ⚠️ **Se pierden** (salvo que el dueño las recuerde y las rehaga) |
| Imágenes | **No se tocan**: viven en Cloudinary, las URLs están en los datos |

La BD de Render se borra sola en ~13 días; no hay nada rescatable de ella
sin pagar. Render web (gratis) sigue sirviendo el código viejo `d0320df`
hasta que se toque; auto-deploy está desactivado, ningún push lo mueve.

## 2. Veredicto serv00 (revisado el 21/oct/2026 en docs.serv00.com)

| Concepto | Free |
| --- | --- |
| Disco / tráfico | 3 GB SSD / ilimitado |
| Webs / BD | 100 / **3 PostgreSQL (v16)**, 10 MySQL, 3 MongoDB |
| Procesos / RAM | 15–20 del sistema / **512 MB** |
| Python | 3.8–3.12 (default 3.11) — usar **3.12** |
| Django | Soportado oficialmente vía **Phusion Passenger** |
| Extras | SSH, crontab, git/SVN, Let's Encrypt, backups diarios (7 días), UE (Polonia) |
| Caducidad | Cuentas con caducidad a 10 años; purgan cuentas vacías/inactivas |

**Trampas conocidas (las honestas):**

1. **Registro lleno**: los servidores se llenan («account limit reached»);
   hay que reintentar más tarde entre los paneles panel0–panel16.
2. **512 MB de RAM**: NO cabe compilar el frontend (npm/vite) en el
   servidor. El build se hace en local y se sube `frontend/dist` (el flujo
   con Render ya era medio así).
3. **CPU compartida**: `cargar_fichas` (~16.136 registros) tardará **horas**
   → se lanza con `nohup` y se deja correr; es idempotente y reanudable.
4. **Inactividad**: si la cuenta se queda vacía meses, pueden limpiarla.
   Mantenerla viva (visitas al sitio o un cron de comprobación).
5. **FreeBSD**: `psycopg2` y `Pillow` compilan desde fuente (no hay wheels);
   en su jail están las librerías de cabecera. Si algo falla, el «soporte»
   es su foro (forum.serv00.com).
6. **Sin SLA**: sirve para beta; si un día crece, se paga Render/otro.

Conclusión: **encaja**. Django + PostgreSQL + SSH + cron gratis, sin
tarjeta y sin reloj de caducidad para la BD.

## 3. Arquitectura del despliegue

- Repo clonado en `~/BuscandoAndo`; el proyecto Django (con `manage.py`) se
  publica como `~/domains/DOMAIN/public_python` (symlink al backend; si
  Passenger no sigue el symlink, se hace `rsync backend/ → public_python/`).
- **Passenger** arranca `backend/passenger_wsgi.py` (nuevo en el repo): lee
  `env.production` (secrets, gitignored, solo en el servidor) y carga
  `config.settings`. Se reinicia con `devil www DOMAIN restart`.
- **nginx** sirve desde disco todo lo que haya en
  `public_python/public/*` → `STATIC_ROOT` apunta a
  `.../public_python/public/static` (collectstatic). Los assets con hash de
  la SPA los sigue sirviendo Django (`serve_react` lee `frontend/dist`).
- **robots.txt sigue dinámico** (vista con respaldo, requisito de la
  auditoría SEO): NO se crea `public/robots.txt` — si existiera un fichero
  ahí, nginx lo sirvería y taparía la vista.
- BD: PostgreSQL de serv00 en `pgsqlN.serv00.com:5432` (variables `DB_*`).
- Imágenes: Cloudinary igual que siempre (`CLOUDINARY_*` en env).
- `SITIO_URL` = el dominio final (canonical, og:url y sitemap salen de ahí).

## 4. Plan de ejecución (lo hace el agente por SSH)

**0. Del dueño** (lo único manual): cuenta en serv00.com (email), pegar la
clave SSH pública que da el agente (panel o `Login with key`), y decir
login + número de servidor (sX).

**1. Entorno**: virtualenv con python3.12 (panel DevilWEB → virtualenvs, o
CLI `devil`; confirmar sintaxis viva en docs.serv00.com/Python) y
`~/venvs/ba/bin/pip install -r backend/requirements.txt`.

**2. Base de datos**: `devil pgsql db add buscandoando` + contraseña
(`devil pgsql passwd buscandoando`). Anotar host `pgsqlN.serv00.com`.

**3. Código**: `git clone https://github.com/yanle4209/BuscandoAndo.git`
(trae `backend/data/fichas_nacionales.ndjson.gz` y las migraciones).

**4. Layout**: `ln -s ~/BuscandoAndo/backend
~/domains/DOMAIN/public_python` (fallback rsync, ver §2).

**5. Frontend**: build en local (`cd frontend && npm run build`) y subir el
`dist` por scp/sftp a `~/BuscandoAndo/frontend/dist`.

**6. `env.production`** en la raíz del backend (gitignored):

```
SECRET_KEY=<generada>
DEBUG=0
USE_POSTGRES=1
DB_NAME=buscandoando
DB_USER=<login BD>
DB_PASSWORD=<passwd BD>
DB_HOST=pgsqlN.serv00.com
DB_PORT=5432
ALLOWED_HOSTS=LOGIN.serv00.net
CSRF_TRUSTED_ORIGINS=https://LOGIN.serv00.net
CORS_ALLOWED_ORIGINS=https://LOGIN.serv00.net
SITIO_URL=https://LOGIN.serv00.net
STATIC_ROOT=/usr/home/LOGIN/domains/DOMAIN/public_python/public/static
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

**7. Estáticos y datos**: `collectstatic --noinput`, `migrate`,
`setup_admin`, `load_initial_data`.

**8. Import nacional**: `nohup python manage.py cargar_fichas
data/fichas_nacionales.ndjson.gz > logs/import.log 2>&1 &` (horas; sin
riesgo para el sitio aunque esté sirviendo: es la BD nueva, no una ajena).

**9. Dominio y SSL**: `devil www add DOMINIO -t python` apuntando al
binario del virtualenv (entorno `production`), forzar SSL (Let's Encrypt,
gratis, automático). Confirmar en vivo si DOMINIO acepta el subdominio
propio `LOGIN.serv00.net` (debe ser así: es el que te delegan).

**10. Batería de verificación** (igual que la de Render): `/`,
`/admin` (login Turbo), `/robots.txt`, `/sitemap.xml`, una ficha, la API,
el panel SEO, y logout con Turbo.

## 5. Operación diaria (después de la beta)

- Cambios de código: commit + push a GitHub; en el servidor `git pull`;
  si cambió el frontend: build local + subir `dist`; luego `collectstatic`
  (si toca estáticos) y `devil www DOMINIO restart`.
- Todo eso lo puede ejecutar el agente con solo pedirlo.

## 6. Riesgos y planes B

| Riesgo | Plan B |
| --- | --- |
| Servidores llenos al registrar | Reintentar (panel0–16); probar a distintas horas |
| `psycopg2`/`Pillow` no compilan | Foro serv00 (piden instalar módulos) o bajar a versiones con wheels |
| Cuenta purgada por inactividad | Cron local de comprobación mensual + visitas |
| La beta despega y hay que pagar | Volver a Render/otro con DB de pago; el repo ya está listo para DATABASE_URL |

## 7. Pendiente fuera de alcance

- `export-json` de fichas: en Render daba 500 por tamaño; en serv00 se
  probará con el SSH/Shell disponibles.
- Borrar el proyecto de Render (web gratis + BD caducada) cuando serv00
  esté verificado — decisión del dueño, sin prisa (borrado automático de
  la BD en ~13 días).
