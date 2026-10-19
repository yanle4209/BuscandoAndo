# -*- coding: utf-8 -*-
"""Cabeceras de seguridad que Django no trae configuradas solo.

En produccion el sitio es uno solo —React y el admin los sirve el mismo
Django—, asi que la politica puede ser cerrada. Con esto se cubre el
efecto de un XSS cargado por terceros: aunque llegue a ejecutarse, no
podra hablar con ningun otro origen ni incrustar nada de fuera.
"""
from django.conf import settings


class CabecerasSeguridadMiddleware:
    """Content-Security-Policy en toda respuesta (solo en produccion).

    Notas de la politica:

    * ``script-src 'self'`` — los bundles son propios (Vite) y el admin
      de Django tambien; nada de scripts de terceros ni inline.
    * ``style-src 'self' 'unsafe-inline' https://unpkg.com`` — React
      pinta atributos ``style`` en línea, y el index enlaza el
      leaflet.css de unpkg (el mapa del detalle); a futuro conviene
      auto-alojarlo y cerrar esto a 'self'.
    * ``img-src ... https:`` — Cloudinary (fotos) y las teselas del
      mapa (Leaflet/osmdroid) vienen por https.
    * ``connect-src 'self'`` — toda la API es del mismo origen; Cloudinary
      queda por si el widget subiera desde el navegador.
    * ``frame-ancestors 'none'`` — refuerza ``X_FRAME_OPTIONS = 'DENY'``
      contra el clickjacking (el header viejo ya no le hace caso a
      navegadores modernos).
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://res.cloudinary.com; "
        "worker-src 'self' blob:; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.DEBUG:
            # setdefault: si una vista ya puso su propia politica, se
            # respeta y no se pisa.
            response.setdefault('Content-Security-Policy', self.CSP)
        return response
