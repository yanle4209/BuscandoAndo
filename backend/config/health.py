"""Health check para Render.

En que consiste
---------------
``render.yaml`` apunta ``healthCheckPath`` a ``/api/health/``. Render lo
llama cada pocos segundos y marca el servicio como caido si responde
5xx o si tarda demasiado (por eso sustituye al ``/admin/`` anterior:
este endpoint es baratísimo de responder).

Decisiones de diseno (y por que)
--------------------------------
1. **Toca la base de datos, pero el codigo de estado solo habla del
   proceso.** La consulta —``SELECT 1``— es la que mantiene viva la
   conexion y el calculo de la BD: sin ella, el primer toque de
   cualquier peticion despues de unos minutos quietos paga el
   despertar (~0,8 s medidos en produccion). Si la BD falla, el error
   se recoge en el campo ``db`` del cuerpo y la respuesta sigue siendo
   200: un health check mide "esta instancia de gunicorn responde",
   no "los datos estan bien". Si el 5xx dependiera de la BD, Render
   reiniciaria el servicio en bucle durante un corte y empeoraria el
   problema (leccion del incidente del 20/oct, DISENO.md 15.5). Hay
   tests para las DOS mitades: que consulta y que aun asi no se pone
   rojo si la BD esta caida.

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

from django.db import connection
from django.http import JsonResponse

#: SHA del despliegue. Render la pone en build y en runtime;
#: fuera de Render (local, tests) no existe, y devolvemos "local".
COMMIT_ENV_VAR = "RENDER_GIT_COMMIT"


def current_commit() -> str:
    """SHA del commit desplegado, o "local" si no corremos en Render."""
    return os.environ.get(COMMIT_ENV_VAR) or "local"


def health(request):
    """GET /api/health/  ->  estado minimo del servicio.

    El ``SELECT 1`` no decide nada: su unico trabajo es que la BD
    reciba trafico seguido y no se suspenda sola (decision 1 del
    modulo). El resultado viaja en el cuerpo como ``db``, jamas en el
    codigo de estado.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception as exc:  # cualquier fallo: el proceso sigue vivo
        db = "error (%s)" % type(exc).__name__
    response = JsonResponse(
        {
            "status": "ok",
            "service": "buscandoando",
            "commit": current_commit(),
            "db": db,
            # Sirve para confirmar que la respuesta es de AHORA y no
            # viene de la cache del CDN.
            "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    response["Cache-Control"] = "no-store"
    return response
