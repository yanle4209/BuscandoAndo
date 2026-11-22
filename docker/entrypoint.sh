#!/bin/sh
# Entrypoint de BuscandoAndo para Docker / Coolify.
#
# Que hace, en orden y por que:
#   1. Arranca como root solo para preparar los volumenes (Docker crea
#      los volumenes con dueno root y el usuario "app" no podria escribir
#      las fotos). Luego baja a "app" con gosu y no vuelve a subir.
#   2. Espera a la base de datos. En un compose, "depends_on" espera a
#      que el contenedor de Postgres exista, no a que acepte conexiones:
#      sin esta espera el primer migrate se cae en el arranque en frio.
#   3. migrate, collectstatic, superusuario y datos iniciales. Los tres
#      ultimos son idempotentes (lo dicen sus propios comandos), asi que
#      reiniciar el contenedor no duplica ni borra nada.
#   4. Opcionalmente carga las fichas nacionales (CARGAR_FICHAS=1). Va
#      apagado por defecto: son ~1.800 filas y en Render se decidio
#      correrlo a mano, nunca en el arranque (DISENO.md 15.5).
#   5. Exec a gunicorn. exec, no llamada normal: gunicorn queda como PID
#      1 y recibe el SIGTERM de Docker/Coolify, cerrando sin cortar
#      peticiones a medias.

set -e

cd /app/backend

# --- 1. Permisos del volumen ------------------------------------------
if [ "$(id -u)" = "0" ]; then
    : "${STATIC_ROOT:=/app/backend/staticfiles}"
    : "${MEDIA_ROOT:=/app/backend/media}"
    mkdir -p "$STATIC_ROOT" "$MEDIA_ROOT"
    # || true: si el volumen es de solo lectura el contenedor debe seguir
    # arrancando (con Cloudinary el media ni se toca) en vez de morir.
    chown -R app:app "$STATIC_ROOT" "$MEDIA_ROOT" 2>/dev/null || true

    if command -v gosu >/dev/null 2>&1; then
        exec gosu app:app "$0" "$@"
    fi
    echo "AVISO: gosu no esta disponible; se continua como root." >&2
fi

# --- 2. Esperar a la base de datos ------------------------------------
# Se prueba con el propio Django (connection.ensure_connection) en vez
# de nc/pg_isready: usa EXACTAMENTE la configuracion que usara el sitio
# (DATABASE_URL u opcion DB_*), asi que un error de credenciales se ve
# aqui y no como un 500 en la primera visita.
if [ "${ESPERAR_BD:-1}" = "1" ]; then
    intentos=0
    maximo="${ESPERAR_BD_INTENTOS:-30}"
    until python - <<'PY'
import os, sys
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
try:
    django.setup()
    from django.db import connection
    connection.ensure_connection()
except Exception as exc:
    print(f"BD no disponible: {type(exc).__name__}", file=sys.stderr)
    sys.exit(1)
PY
    do
        intentos=$((intentos + 1))
        if [ "$intentos" -ge "$maximo" ]; then
            echo "ERROR: la base de datos no respondio tras $maximo intentos." >&2
            exit 1
        fi
        echo "Esperando base de datos ($intentos/$maximo)..."
        sleep 2
    done
fi

# --- 3. Preparacion idempotente ---------------------------------------
echo "== migrate =="
python manage.py migrate --noinput

echo "== collectstatic =="
# WhiteNoise sirve los estaticos desde STATIC_ROOT; el manifest con
# hash se genera aqui, en cada arranque, para que nunca quede uno viejo.
python manage.py collectstatic --noinput

echo "== setup_admin =="
# Sin DJANGO_SUPERUSER_PASSWORD no crea nada y lo avisa (por diseno).
python manage.py setup_admin

echo "== load_initial_data =="
# Solo carga si la base esta vacia; con datos existentes se salta.
python manage.py load_initial_data

if [ "${CARGAR_FICHAS:-0}" = "1" ]; then
    echo "== cargar_fichas (CARGAR_FICHAS=1) =="
    python manage.py cargar_fichas data/fichas_nacionales.ndjson.gz
fi

# --- 4. Comando explicito, si lo hay ----------------------------------
if [ "$#" -gt 0 ]; then
    echo "== comando: $* =="
    exec "$@"
fi

# --- 5. Gunicorn ------------------------------------------------------
# gthread 2x4 = 8 peticiones a la vez. Lo mismo que Render: la prueba
# de carga del 9/nov midio ~5,4 req/s con 1 worker y colas de 10-14 s
# con 30 usuarios; con esto se solapan las esperas de red a la BD.
echo "== gunicorn en 0.0.0.0:${PORT:-8000} =="
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --worker-class gthread \
    --workers "${WEB_CONCURRENCY:-2}" \
    --threads "${WEB_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
