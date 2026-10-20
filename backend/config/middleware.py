# -*- coding: utf-8 -*-
"""Cabeceras de seguridad que Django no trae configuradas solo.

En produccion el sitio es uno solo —React y el admin los sirve el mismo
Django—, asi que la politica puede ser cerrada. Con esto se cubre el
efecto de un XSS cargado por terceros: aunque llegue a ejecutarse, no
podra hablar con ningun otro origen ni incrustar nada de fuera.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from businesses.levantamiento import _ip


class CabecerasSeguridadMiddleware:
    """Content-Security-Policy en toda respuesta (solo en produccion).

    Notas de la politica:

    * ``script-src 'self'`` — los bundles son propios (Vite) y el admin
      de Django tambien; nada de scripts de terceros ni inline.
    * ``style-src 'self' 'unsafe-inline'`` — React pinta atributos
      ``style`` en línea; el leaflet.css ya va empaquetado (lo importa
      MapView.jsx y lo sirve el propio bundle, igual que el del admin),
      asi que no queda ningun tercero aqui.
    * ``img-src ... https:`` — Cloudinary (fotos) y las teselas del
      mapa (Leaflet/osmdroid) vienen por https.
    * ``connect-src 'self' ...`` — la API es del mismo origen y
      Cloudinary por si el widget subiera desde el navegador;
      nominatim es el geocodificador del MAPA DEL ADMIN
      (business_admin.js), que sin esto quedaria bloqueado.
    * ``frame-ancestors 'none'`` — refuerza ``X_FRAME_OPTIONS = 'DENY'``
      contra el clickjacking (el header viejo ya no le hace caso a
      navegadores modernos).
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://res.cloudinary.com "
        "https://nominatim.openstreetmap.org; "
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


class ThrottleLoginAdmin:
    """Freno de intentos contra el login del admin (auditoria 19/oct).

    Delante no hay un Cloudflare propio: el del sitio es el de Render,
    que no admite reglas nuestras, asi que el freno vive aqui.

    Cuenta **fallos**, no intentos: un POST a ``/admin/login/`` que
    Django vuelve a pintar con error (200) cuenta; un redirect (302),
    que es como se reconoce un login bueno, borra. Dos contadores en
    cache:

    * **por IP**:      5 fallos  -> 10 min sin validar contrasenas;
    * **por usuario**: 25 fallos -> 15 min. El techo, lo bastante alto
      para que un escaner aleatorio no candade la cuenta a posta y lo
      justo para que un ataque que cambie de IP no se lucre.

    Cuando salta el freno la contrasena **ni se comprueba** (429 con
    ``Retry-After``): un diccionario no gana nada probando contra el
    hash. Un login bueno borra sus contadores, el formulario (GET) nunca
    se frenea, y los intentos que llegan mientras dura el bloqueo **no
    alargan la espera** — nadie puede condenar la cuenta a candado
    permanente.

    Los contadores viven en la cache del proceso, asi que un reinicio
    del servicio los borra: aceptable para un freno — lo que no se
    pierde en ningun reinicio es la contrasena buena.
    """

    RUTA = '/admin/login/'

    FALLOS_POR_IP = 5
    SEGUNDOS_IP = 10 * 60
    FALLOS_POR_USUARIO = 25
    SEGUNDOS_USUARIO = 15 * 60

    PREFIJO = 'ba-login:'

    def __init__(self, get_response):
        self.get_response = get_response

    def _claves(self, request, usuario):
        """(clave, ventana, techo) de cada contador que le toca."""
        claves = []
        ip = _ip(request)
        if ip:
            claves.append(('ip:' + ip, self.SEGUNDOS_IP,
                           self.FALLOS_POR_IP))
        if usuario:
            claves.append(('usuario:' + usuario.lower(),
                           self.SEGUNDOS_USUARIO,
                           self.FALLOS_POR_USUARIO))
        return claves

    def _subir(self, clave, ventana):
        if cache.add(clave, 1, timeout=ventana):
            return 1
        try:
            return cache.incr(clave)
        except ValueError:
            # expiro justo entre el add y el incr: se empieza de cero.
            cache.set(clave, 1, timeout=ventana)
            return 1

    def _respuesta_de_bloqueo(self, ventana):
        respuesta = HttpResponse(
            '<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<title>Demasiados intentos</title></head><body>'
            '<h1>Demasiados intentos fallidos</h1>'
            '<p>El acceso al panel esta frenado por unos minutos. '
            'Vuelve a intentarlo mas tarde.</p></body></html>',
            status=429,
            content_type='text/html; charset=utf-8')
        respuesta['Retry-After'] = str(ventana)
        return respuesta

    def __call__(self, request):
        es_intento = request.method == 'POST' and request.path == self.RUTA
        usuario = ''
        if es_intento:
            usuario = (request.POST.get('username') or '').strip()
            for clave, ventana, techo in self._claves(request, usuario):
                if cache.get(self.PREFIJO + clave, 0) >= techo:
                    # Antes de CsrfViewMiddleware y de la vista: la
                    # contrasena no se toca.
                    return self._respuesta_de_bloqueo(ventana)

        respuesta = self.get_response(request)

        if es_intento:
            if 300 <= respuesta.status_code < 400:
                for clave, _, _ in self._claves(request, usuario):
                    cache.delete(self.PREFIJO + clave)
            elif respuesta.status_code == 200:
                for clave, ventana, _ in self._claves(request, usuario):
                    self._subir(self.PREFIJO + clave, ventana)
        return respuesta
