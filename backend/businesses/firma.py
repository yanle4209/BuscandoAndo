"""Quien firma un pedido.

Compartido por el canal de envio (§11.5) y el reporte por municipio
(§11.1): si cada uno leyera el token a su manera, un mismo token podria
servir para una cosa y no para la otra sin que se note, y bloquear a un
colaborador dejaria media pieza abierta y media cerrada.

El token es una **firma, no una sesion**: por eso se acepta solo en
cabecera (en la URL se quedaria en el historial y en los registros del
servidor), y por eso que este inactivo lo apaga a el y solo a el.
"""
from .models import Colaborador

# Copia exacta de la cabecera, para que quien la recibe pueda mandarla sin
# adivinar si va en minusculas o con guion.
CABECERA = 'X-Colaborador-Token'
ESQUEMA_BEARER = 'bearer '

AUTORIZACION = 'Authorization'


def token_de(request):
    """El token que trae la peticion, en ``X-Colaborador-Token`` o
    ``Authorization: Bearer``. Vacio si no trae ninguno de los dos."""
    token = request.headers.get(CABECERA, '').strip()
    if not token:
        autorizacion = request.headers.get(AUTORIZACION, '')
        if autorizacion[:len(ESQUEMA_BEARER)].lower() == ESQUEMA_BEARER:
            token = autorizacion[len(ESQUEMA_BEARER):].strip()
    return token


def colaborador_de(request):
    """El colaborador activo que firma esta peticion, o ``None``.

    Que este inactivo devuelve tambien ``None``: apagar el token de uno
    es como no tenerlo, sin tocar a los demas (§11.5).
    """
    token = token_de(request)
    if not token:
        return None
    return Colaborador.objects.filter(token=token, activo=True).first()
