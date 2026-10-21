# -*- coding: utf-8 -*-
"""Punto de entrada WSGI para Phusion Passenger (serv00.com).

En serv00 la pagina ``python`` la arranca Passenger: busca este fichero
en la raiz del proyecto (``public_python``) y ejecuta ``application``.
No hay interfaz de variables de entorno como en Render — los secrets
viven en ``env.production`` (gitignored; existe solo en el servidor),
en formato ``CLAVE=valor``, y se cargan ANTES de tocar los settings.
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Passenger ejecuta este fichero con el cwd dentro del proyecto, pero
# `config` tiene que estar importable de forma explicita.
sys.path.insert(0, str(BASE))

env_file = BASE / 'env.production'
if env_file.exists():
    for linea in env_file.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, _, valor = linea.partition('=')
        os.environ.setdefault(clave.strip(), valor.strip())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
