"""Health check para Render.

En que consiste
---------------
``render.yaml`` apunta ``healthCheckPath`` a ``/api/health/``. Render lo
llama cada pocos segundos y marca el servicio como caido si responde
5xx o si tarda demasiado (por eso sustituye al ``/admin/`` anterior:
este endpoint es baratísimo de responder).

Decisiones de diseno (y por que)
--------------------------------
1. **NO consulta la base de datos.** Un health check mide "esta
   instancia de gunicorn responde", no "los datos estan bien". Si la
   BD se pone lenta, con una consulta aqui Render reiniciaria el
   servicio en bucle y empeoraria el problema. Hay un test que lo
   garantiza.

2. **``Cache-Control: no-store``.** Detras del dominio hay un CDN
   (Cloudflare). Sin esta cabecera podríamos recibir un 200 CACHEADO
   de un deploy anterior y creer que el codigo nuevo esta vivo cuando
   en realidad estamos mirando la version vieja.

3. **Devuelve el commit.** ``RENDER_GIT_COMMIT`` es una variable que
   Render inyecta en cada despliegue (build y runtime). Un ``curl``
   basta para saber QUE codigo esta en produccion:

       curl -s https://buscandoando.onrender.com/api/health/

   -> {"status":"ok","commit":"8b3e896...", ...}
"""

import os
from datetime import datetime, timezone

from django.http import JsonResponse

#: SHA del despliegue. Render la pone en build y en runtime;
#: fuera de Render (local, tests) no existe, y devolvemos "local".
COMMIT_ENV_VAR = "RENDER_GIT_COMMIT"


def current_commit() -> str:
    """SHA del commit desplegado, o "local" si no corremos en Render."""
    return os.environ.get(COMMIT_ENV_VAR) or "local"


def health(request):
    """GET /api/health/  ->  estado minimo del servicio."""
    response = JsonResponse(
        {
            "status": "ok",
            "service": "buscandoando",
            "commit": current_commit(),
            # Sirve para confirmar que la respuesta es de AHORA y no
            # viene de la cache del CDN.
            "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    response["Cache-Control"] = "no-store"
    return response
