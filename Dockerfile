# syntax=docker/dockerfile:1.7
#
# BuscandoAndo — imagen unica (Django + React compilado).
#
# Dos etapas para que la imagen final no lleve Node ni node_modules:
#   1. frontend: Vite compila React a dist/.
#   2. runtime:  Python 3.14 con las dependencias y el dist copiado.
#
# El backend sirve el SPA el mismo (views.serve_react), asi que no hace
# falta nginx: una sola pieza, un solo health check, un solo log.
#
# Probado contra Python 3.14 / Django 5.2.18, las versiones fijadas en
# backend/requirements.txt.

############################# 1. Frontend #############################
FROM node:22-alpine AS frontend

WORKDIR /build

# Solo los manifiestos primero: mientras no cambien las dependencias,
# esta capa se reutiliza y el build no vuelve a bajar node_modules.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# El frontend llama a /api con rutas relativas (src/api/axios.js), asi
# que NO necesita ninguna variable en tiempo de build.
RUN npm run build


############################# 2. Runtime ##############################
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PORT=8000

# curl: health check del compose y depuracion dentro del contenedor.
# gosu: el entrypoint arranca como root (para arreglar permisos del
# volumen de media) y baja a usuario sin privilegios antes de tocar
# Django.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias antes que el codigo: capa cacheable.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Codigo del backend + build del frontend.
# settings.REACT_BUILD_DIR = BASE_DIR.parent / "frontend" / "dist",
# o sea /app/frontend/dist con esta disposicion. No cambiar sin tocar
# settings.py.
COPY backend/ /app/backend/
COPY --from=frontend /build/dist /app/frontend/dist

# Usuario sin privilegios. Los directorios que escriben en caliente
# (staticfiles de collectstatic y media cuando no hay Cloudinary) se
# crean aqui y se ceden; el entrypoint vuelve a ajustar el volumen.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/backend/staticfiles /app/backend/media \
    && chown -R app:app /app

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

WORKDIR /app/backend

EXPOSE 8000

# Sin CMD a proposito: el entrypoint hace migrate + collectstatic +
# admin + datos iniciales y luego lanza gunicorn con los valores de
# entorno (PORT, WEB_CONCURRENCY, WEB_THREADS). Si alguien pasa un
# comando (`docker run ... python manage.py shell`), el entrypoint lo
# ejecuta despues de la preparacion.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
