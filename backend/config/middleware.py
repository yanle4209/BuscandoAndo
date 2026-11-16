# -*- coding: utf-8 -*-
"""Cabeceras de seguridad que Django no trae configuradas solo.

En produccion el sitio es uno solo —React y el admin los sirve el mismo
Django—, asi que la politica puede ser cerrada. Con esto se cubre el
efecto de un XSS cargado por terceros: aunque llegue a ejecutarse, no
podra hablar con ningun otro origen ni incrustar nada de fuera.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from businesses.levantamiento import _ip
from uso.models import registrar


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
    * ``media-src 'self' ...`` — el VIDEO del anuncio de la celda viene
      de Cloudinary: sin esta linea cae a ``default-src 'self'`` y el
      navegador lo bloquea (el <video> falla con "formato y tipo MIME
      compatibles", el mismo sintoma que una URL mala — incidencia
      del 15/nov).
    * ``connect-src 'self' ...`` — la API es del mismo origen y
      Cloudinary por si el widget subiera desde el navegador;
      nominatim es el geocodificador del MAPA DEL ADMIN
      (business_admin.js), que sin esto quedaria bloqueado.
    * ``frame-ancestors 'none'`` — refuerza ``X_FRAME_OPTIONS = 'DENY'``
      contra el clickjacking (el header viejo ya no le hace caso a
      navegadores modernos).
    * ``Permissions-Policy`` (auditoria E) — la web solo usa
      geolocalizacion, y solo para si misma (el buscador R3). Camara,
      microfono, pago y USB quedan apagados: nada de eso se necesita y
      un script colado no debe poder tocarlo.
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' https://res.cloudinary.com; "
        "font-src 'self' data:; "
        "connect-src 'self' https://res.cloudinary.com "
        "https://nominatim.openstreetmap.org; "
        "worker-src 'self' blob:; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    # Lo que la pagina NO pide nunca se le niega por delante. La
    # geolocalizacion si: sin ella no hay buscador (R1/R3).
    PERMISOS = (
        'geolocation=(self), camera=(), microphone=(), payment=(), usb=()'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.DEBUG:
            # setdefault: si una vista ya puso su propia politica, se
            # respeta y no se pisa.
            response.setdefault('Content-Security-Policy', self.CSP)
            response.setdefault('Permissions-Policy', self.PERMISOS)
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

    def _respuesta_de_bloqueo(self, ventana, request):
        # Cada bloqueo suma uno al contador del dia (evento 'freno'),
        # igual que los 429 de los frenos de la API.
        registrar('freno', request)
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
                    return self._respuesta_de_bloqueo(ventana, request)

        respuesta = self.get_response(request)

        if es_intento:
            if 300 <= respuesta.status_code < 400:
                for clave, _, _ in self._claves(request, usuario):
                    cache.delete(self.PREFIJO + clave)
            elif respuesta.status_code == 200:
                for clave, ventana, _ in self._claves(request, usuario):
                    self._subir(self.PREFIJO + clave, ventana)
        return respuesta


class _ThrottlePorIP:
    """Receta comun de los frenos por IP: cuenta en la cache del proceso.

    Vive aqui, y no en DRF, por lo mismo que ``ThrottleLoginAdmin``:
    el techo no debe depender de que la vista pase por el ``initial()``
    del framework ni de que quien llama este autenticado. Los contadores
    son del proceso (un reinicio los borra), igual que el freno del
    login: aceptable para un techo, que es lo que hace.

    El contador sube **tambien cuando la peticion es rechazada**: el
    tanteo es parte del abuso. Al llegar al techo, la peticion ni llega
    a la vista (429 JSON con ``Retry-After``).
    """

    RUTA = ''
    METODO = 'POST'
    TECHO = 30
    VENTANA = 60 * 60
    PREFIJO = 'ba:'
    MENSAJE = ('Demasiados envios: espera unos minutos y vuelve a '
               'intentarlo.')

    def __init__(self, get_response):
        self.get_response = get_response

    def _clave(self, request):
        ip = _ip(request)
        if not ip:
            return None
        return self.PREFIJO + 'ip:' + ip

    def _subir(self, clave):
        if cache.add(clave, 1, timeout=self.VENTANA):
            return
        try:
            cache.incr(clave)
        except ValueError:
            # expiro justo entre el add y el incr: se empieza de cero.
            cache.set(clave, 1, timeout=self.VENTANA)

    def _bloqueada(self, request):
        # Cada 429 suma uno al contador del dia (evento 'freno'): asi el
        # panel de uso ensena cuantas veces salto cada freno y el admin
        # ve si hay un ataque en curso o si los techos estan cortos.
        # La metrica nunca tumba la respuesta (registrar no lanza).
        registrar('freno', request)
        respuesta = JsonResponse({'detail': self.MENSAJE}, status=429)
        respuesta['Retry-After'] = str(self.VENTANA)
        return respuesta

    def __call__(self, request):
        activa = (request.method == self.METODO
                  and request.path == self.RUTA)
        clave = self._clave(request) if activa else None

        # Antes de la vista: lo que llega de mas ni se valida.
        if clave and cache.get(clave, 0) >= self.TECHO:
            return self._bloqueada(request)

        respuesta = self.get_response(request)
        if clave:
            self._subir(clave)
        return respuesta


class ThrottleCorrecciones(_ThrottlePorIP):
    """Freno de envios al formulario publico «Corregir» (auditoria E).

    ``POST /api/corrections/`` es PUBLICO a proposito: cualquier
    visitante puede avisar de un dato malo sin login. Sin techo, eso
    tambien significa que un bot puede inundar la bandeja del admin en
    minutos — el mensaje de «demasiados envios» del frontend existia,
    pero nada del servidor lo devolvia nunca.

    30 por hora por IP. Un humano normal no se acerca (el formulario pide
    campo y una frase); el spam sostenido se corta en seco. Solo al
    ``create``: el listado es solo staff y no toca esta cuenta.

    En pruebas la suite entera manda ~18 envios desde 127.0.0.1, por
    debajo del techo: el limite no se cruza solo. El test del freno
    pone el contador al techo a mano y lo borra al terminar, asi no
    depende del orden.
    """

    RUTA = '/api/corrections/'
    METODO = 'POST'
    TECHO = 30
    VENTANA = 60 * 60
    PREFIJO = 'ba-correcciones:'


class ThrottleInteres(_ThrottlePorIP):
    """Freno del contador publico del banner de fuera de fase.

    ``POST /api/interes/`` es publico y solo suma una metrica, pero sin
    techo un bot puede inflar ``aviso_interes`` — que es justamente el
    contador que decide donde abrir despues (DISENO.md 13) — y el admin
    acabaria leyendo un interesse que nadie tuvo.

    30 por hora por IP: una persona pulsa el boton una vez; el spam
    sostenido se corta antes de tocar la metrica.
    """

    RUTA = '/api/interes/'
    METODO = 'POST'
    TECHO = 30
    VENTANA = 60 * 60
    PREFIJO = 'ba-interes:'
    MENSAJE = ('Demasiados avisos: espera unos minutos y vuelve a '
               'intentarlo.')


class ThrottlePendientes(_ThrottlePorIP):
    """Freno de la lectura del reporte de pendientes (DISENO.md 11.1).

    ``GET /api/pendientes/`` es la consulta mas cara del sitio: calcula
    el trabajo municipio a municipio sobre las 158 cabeceras y, sin
    ``?municipio=``, entero. Requiere token de colaborador o sesion de
    admin (§11-i), pero sin techo un rastreador lo pedia una y otra vez
    — cada respuesta es un repaso completo del padron.

    60 por hora por IP: de sobra para una sesion de trabajo real (el
    reporte se relee al completar cada ficha) y un tope claro para
    quien solo quiere golpear. La suite manda ~12 lecturas desde
    127.0.0.1, por debajo del techo.
    """

    RUTA = '/api/pendientes/'
    METODO = 'GET'
    TECHO = 60
    VENTANA = 60 * 60
    PREFIJO = 'ba-pendientes:'
