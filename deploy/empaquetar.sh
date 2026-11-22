#!/usr/bin/env bash
# Empaqueta BuscandoAndo para llevarlo a otra maquina.
#
#   ./deploy/empaquetar.sh                 # -> ../buscandoando-deploy-AAAAMMDD.tar.gz
#   ./deploy/empaquetar.sh /ruta/salida.tgz
#
# Que deja fuera y por que:
#   .venv, node_modules, dist   -> se reconstruyen en la maquina destino
#   db.sqlite3                  -> datos locales, no son el proyecto
#   media/                      -> 26 MB de fotos; si se necesitan, se
#                                  copian aparte o se usa Cloudinary
#   staticfiles/                -> lo regenera collectstatic
#   .env, *.log                 -> secretos y ruido
#
# Lo que SI viaja: codigo, migraciones, fixture inicial, fichas
# nacionales (441 KB) y los ficheros de despliegue (Dockerfile,
# docker-compose.yaml, docker/entrypoint.sh, .env.coolify.example,
# COOLIFY.md y este script).
#
# El resultado es autocontenido para `docker compose up -d --build`.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOMBRE="buscandoando-deploy-$(date +%Y%m%d)"
SALIDA="${1:-$(dirname "$RAIZ")/$NOMBRE.tar.gz}"

# Ruta absoluta: el tar se crea desde cualquier directorio de trabajo.
case "$SALIDA" in
    /*) ;;
    *) SALIDA="$(pwd)/$SALIDA" ;;
esac

for requerido in Dockerfile docker-compose.yaml docker/entrypoint.sh; do
    if [ ! -f "$RAIZ/$requerido" ]; then
        echo "ERROR: falta $requerido en $RAIZ" >&2
        exit 1
    fi
done

echo "Origen : $RAIZ"
echo "Destino: $SALIDA"
echo

# OJO con los patrones de .env: se excluyen uno a uno, no con ".env.*",
# porque ".env.coolify.example" SI tiene que viajar (es la plantilla).
tar -czf "$SALIDA" \
    -C "$RAIZ" \
    --exclude='./.git' \
    --exclude='./.github' \
    --exclude='./.opencode' \
    --exclude='./.vscode' \
    --exclude='./.idea' \
    --exclude='./.venv' \
    --exclude='./backend/.venv' \
    --exclude='./backend/db.sqlite3' \
    --exclude='./backend/media' \
    --exclude='./backend/staticfiles' \
    --exclude='./backend/public' \
    --exclude='./backend/scripts_antiguos' \
    --exclude='./backend/__pycache__' \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.log' \
    --exclude='./frontend/node_modules' \
    --exclude='./frontend/dist' \
    --exclude='./frontend/.vite' \
    --exclude='./android' \
    --exclude='./.env' \
    --exclude='./.env.local' \
    --exclude='./.env.development' \
    --exclude='./.env.production' \
    --exclude='./.env.prod' \
    --exclude='./backend/.env' \
    --exclude='./backend/config/.env' \
    --exclude='./env.production' \
    .

TAM="$(du -h "$SALIDA" | cut -f1)"
echo "Listo: $SALIDA ($TAM)"
echo
echo "En la maquina destino:"
echo "  mkdir -p /opt/buscandoando && cd /opt/buscandoando"
echo "  tar -xzf $(basename "$SALIDA")"
echo "  cp .env.coolify.example .env     # rellenar SECRET_KEY y POSTGRES_PASSWORD"
echo "  docker compose up -d --build"
