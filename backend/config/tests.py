# -*- coding: utf-8 -*-
"""Tests de la raiz de backend: health check de Render y la vista SPA.

Dos cosas distintas que viven en la misma carpeta:

* ``GET /api/health/`` (config/tests.py, HealthCheckTests): lo que
  protegemos NO es solo "que devuelva 200", sino las tres decisiones
  de diseno de ``config/health.py``: responde sin tocar la BD (para
  que una BD lenta no reinicie el servicio en bucle), no se cachea
  (porque delante hay un CDN) y expone el SHA del commit (para saber
  que codigo hay en produccion).

* ``serve_react`` (ServeReactSeguridadTests): la vista que sirve el
  build de React. La auditoria del 19/oct de 2026 encontro que
  ``GET //etc/passwd`` (ruta absoluta de doble barra, sin normalizar)
  abria el fichero del servidor: pathlib une segmentos absolutos
  reemplazando la base, y la vista comprobaba solo ``exists()``. Se
  llego a leer ``/etc/os-release`` y el ``render.yaml`` entero del
  repositorio desplegado; ``/proc/self/environ`` (con todos los
  secretos) no se filtro por suerte: el fichero tiene tamano 0 y la
  respuesta llegaba vacia. Estos tests fijan la correccion: la ruta
  se aplana y ademas se exige que resuelva dentro del build. Ahora
  ademas una ruta que no es del SPA responde 404 de verdad (auditoria
  C: el 200 universal era un soft-404).

* El SEO on-page (SeoTests): ``serve_react`` inyecta titulo,
  description, Open Graph y canonical por ruta en el servidor, con
  los datos reales de la ficha; ``/sitemap.xml`` se genera desde la
  base ya filtrado a las provincias de fase.
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext, override_settings

from .health import current_commit

# El admin maquilla las hojas con el storage con manifest, que solo
# resuelve despues de `collectstatic`: en los tests no hay manifest y la
# pagina de login ni llegaria a pintarse. Mismo tramite que en
# businesses/tests.py (STATIC_SIN_MANIFEST).
STATIC_SIN_MANIFEST = {
    **settings.STORAGES,
    'staticfiles': {'BACKEND':
                    'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# El serve_react vive en la raiz del backend (backend/views.py), no en
# config/, de ahi el import plano.
from views import serve_react

# Fichas para SeoTests (metas por ruta y sitemap).
from businesses.models import Business
from business_images.models import BusinessImage
from business_locations.models import BusinessLocation
from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

URL = '/api/health/'

#: Nombre EXACTO de la variable que Render inyecta con el SHA del
#: commit (render.com/docs/environment-variables). Va escrita a mano
#: aqui, y NO se importa de config/health.py, a proposito: si alguien
#: renombra la constante del codigo, este test sigue exigiendo el
#: nombre real de Render y el fallo sale aqui, no en produccion.
COMMIT_VAR = 'RENDER_GIT_COMMIT'


class HealthCheckTests(TestCase):

    def test_responde_200_con_estado_ok(self):
        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'buscandoando')

    def test_no_se_puede_cachear(self):
        """Sin esto, Cloudflare podria devolvernos un 200 de un deploy
        anterior y creer que el codigo nuevo ya esta vivo."""
        response = self.client.get(URL)

        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_expone_el_commit_inyectado_por_render(self):
        with mock.patch.dict(os.environ, {COMMIT_VAR: '8b3e896f'}):
            response = self.client.get(URL)

        self.assertEqual(response.json()['commit'], '8b3e896f')

    def test_fuera_de_render_el_commit_es_local(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('RENDER_GIT_COMMIT', None)
            response = self.client.get(URL)

        self.assertEqual(response.json()['commit'], 'local')
        self.assertEqual(current_commit(), 'local')

    def test_no_consulta_la_base_de_datos(self):
        """Garantiza la decision 1 de health.py.

        Si el health check hiciera queries, Render reiniciaria el
        servicio cada vez que la BD fuera lenta: exactamente al reves
        de lo que queremos.
        """
        with CaptureQueriesContext(connection) as queries:
            self.client.get(URL)

        self.assertEqual(len(queries.captured_queries), 0)

    def test_lleva_marca_de_tiempo(self):
        """Sirve para confirmar que la respuesta es de AHORA (y no del
        CDN) cuando se verifica un despliegue."""
        data = self.client.get(URL).json()

        self.assertIn('now', data)
        self.assertNotEqual(data['now'], '')


class ServeReactSeguridadTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        raiz = Path(cls._tmp.name)
        cls.build = raiz / 'dist'
        (cls.build / 'assets').mkdir(parents=True)
        (cls.build / 'index.html').write_text(
            '<!doctype html>INDICE', encoding='utf-8')
        (cls.build / 'assets' / 'app.js').write_text(
            'console.log(1)', encoding='utf-8')
        # Un fichero DELICADO al ladito del build, fuera de el: el que
        # la vista no lo alcance es exactamente lo que se prueba.
        (raiz / 'secreto.txt').write_text(
            'NO SE PUEDE LEER', encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()

    def _respuesta(self, path):
        peticion = RequestFactory().get('/' + path.lstrip('/'))
        with override_settings(REACT_BUILD_DIR=self.build):
            return serve_react(peticion, path=path)

    def _contenido(self, path):
        """El cuerpo: los assets salen streaming (FileResponse) y el
        index de las rutas validas, como HttpResponse ya inyectado."""
        respuesta = self._respuesta(path)
        if hasattr(respuesta, 'streaming_content'):
            return b''.join(respuesta.streaming_content)
        return respuesta.content

    def test_sirve_un_asset_del_build(self):
        """Lo normal: un fichero del build sale tal cual."""
        self.assertEqual(self._contenido('assets/app.js'), b'console.log(1)')

    def test_ruta_absoluta_doble_barra_no_abre_el_servidor(self):
        """//etc/passwd (el ataque real): no es ruta del SPA, asi que la
        vista responde 404 sin construir cuerpo — el fichero no se lee
        ni de pasada."""
        with self.assertRaises(Http404):
            self._respuesta('//etc/passwd')

    def test_ruta_absoluta_codificada_tampoco(self):
        """%2f%2fetc%2fpasswd decodificada es el mismo ataque."""
        with self.assertRaises(Http404):
            self._respuesta('//etc/passwd')

    def test_saltos_de_directorio_no_salen_del_build(self):
        """../secreto.txt resuelve fuera del build: ni se sirve (si lo
        hubiera servido no estariamos ante un 404) ni cae al index."""
        with self.assertRaises(Http404):
            self._respuesta('../secreto.txt')

    def test_ruta_inexistente_devuelve_404(self):
        """Soft-404 (auditoria C): fuera de las rutas de App.jsx no hay
        index — hay un 404 de verdad, para que Google no indexe paginas
        vacias ni el crawler arrastre enlaces muertos."""
        for ruta in ('algo/que/no/existe', 'otra/cosa/valida',
                     'business/otro/nivel'):
            with self.subTest(ruta=ruta):
                with self.assertRaises(Http404):
                    self._respuesta(ruta)

    def test_las_rutas_reales_del_spa_sirven_el_index(self):
        """La excepcion del fallback: lo que React si sabe pintar."""
        self.assertIn(b'INDICE', self._contenido(''))
        self.assertIn(b'INDICE', self._contenido('index.html'))
        self.assertIn(b'INDICE', self._contenido('levantamiento'))


class SeoTests(TestCase):
    """Auditoria C: metas por ruta, soft-404 y sitemap en fase.

    Todo el SEO on-page vive en el servidor (backend/views.py): el
    index se lee y se le inyectan titulo, description, Open Graph y
    canonical con los datos reales de la ficha — sin react-helmet y
    sin esperar a que arranque el JS, que es lo que Google y WhatsApp
    leen. Las fichas fuera de fase abren (DISENO.md 13) pero con
    noindex, y el sitemap solo anuncia lo que el listado enseña.
    """

    #: Index realista: la inyeccion se ancla en <title> y </head>.
    INDEX = (
        '<!doctype html>\n<html lang="es">\n  <head>\n'
        '    <meta charset="UTF-8" />\n'
        '    <title>Titulo por defecto</title>\n'
        '  </head>\n  <body>INDICE</body>\n</html>\n'
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.build = Path(cls._tmp.name) / 'dist'
        cls.build.mkdir()
        (cls.build / 'index.html').write_text(cls.INDEX, encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.revision = PublicationStatus.objects.create(
            name='En Revisión', slug='en-revision')
        cls.category = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')

        cls.en_fase = cls.ficha('La Receta', 'Moca', 'Espaillat',
                                cls.publicado)
        # Con foto: en local no hay config de Cloudinary y la vista no
        # puede caer por eso — la meta usa la tarjeta generica.
        BusinessImage.objects.create(
            business=cls.en_fase,
            image='business_images/2026/09/la_receta.webp')
        cls.fuera = cls.ficha('Dulce Hogar', 'Santo Domingo',
                              'Santo Domingo', cls.publicado)
        cls.sin_publicar = cls.ficha('Ideas Pendientes', 'Moca',
                                     'Espaillat', cls.revision)

    @classmethod
    def ficha(cls, nombre, municipio, provincia, estado):
        biz = Business.objects.create(
            name=nombre,
            description='Descripcion de %s' % nombre,
            short_description='%s: la descripcion corta.' % nombre,
            category=cls.category,
            publication_status=estado,
            operational_status=cls.op_status,
        )
        BusinessLocation.objects.create(
            business=biz, municipality=municipio, province=provincia,
        )
        return biz

    def _get(self, ruta):
        with override_settings(REACT_BUILD_DIR=self.build):
            return self.client.get(ruta)

    def _html(self, ruta):
        return self._get(ruta).content.decode('utf-8')

    # --- soft-404 -------------------------------------------------------

    def test_fuera_de_las_rutas_de_app_js_no_hay_index(self):
        """Lo contrario del 200 universal: solo /, /business/<slug> y
        /levantamiento sirven el index de React."""
        for ruta in ('/ruta-que-no-existe-xyz/', '/business/',
                     '/business/otro/nivel'):
            with self.subTest(ruta=ruta):
                self.assertEqual(self._get(ruta).status_code, 404)

    # --- metas por ruta -------------------------------------------------

    def test_home_lleva_description_og_canonical_y_no_cache(self):
        sitio = settings.SITIO_URL.rstrip('/')
        response = self._get('/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'],
                         'text/html; charset=utf-8')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        html = response.content.decode('utf-8')
        self.assertIn('BuscandoAndo - Encuentra negocios en República '
                      'Dominicana</title>', html)
        self.assertIn('<meta name="description"', html)
        self.assertIn('rel="canonical" href="%s/"' % sitio, html)
        self.assertIn('content="index,follow"', html)
        self.assertIn('og:image" content="%s/og.png"' % sitio, html)
        self.assertIn('name="twitter:card"', html)

    def test_la_ficha_titula_con_nombre_categoria_y_lugar(self):
        sitio = settings.SITIO_URL.rstrip('/')
        response = self._get('/business/%s' % self.en_fase.slug)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('<title>La Receta – Restaurantes en Moca, '
                      'Espaillat | BuscandoAndo</title>', html)
        self.assertIn('canonical" href="%s/business/%s"'
                      % (sitio, self.en_fase.slug), html)
        self.assertIn('la descripcion corta.', html)
        self.assertIn('og.png', html)
        self.assertIn('index,follow', html)

    def test_la_ficha_fuera_de_fase_abre_pero_no_se_indexa(self):
        """El enlace directo no se rompe (DISENO.md 13) pero Google no
        la indexa por su cuenta."""
        response = self._get('/business/%s' % self.fuera.slug)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Dulce Hogar', html)
        self.assertIn('noindex,nofollow', html)

    def test_las_no_publicadas_y_los_slugs_de_ayer_son_404(self):
        """La misma regla que el retrieve de la API."""
        for ruta in ('/business/%s' % self.sin_publicar.slug,
                     '/business/no-existe-esta-ficha'):
            with self.subTest(ruta=ruta):
                self.assertEqual(self._get(ruta).status_code, 404)

    def test_levantamiento_se_sirve_pero_no_se_indexa(self):
        """Herramienta de campo sin enlace publico (DISENO.md 11.5)."""
        response = self._get('/levantamiento')

        self.assertEqual(response.status_code, 200)
        self.assertIn('noindex,nofollow',
                      response.content.decode('utf-8'))

    # --- sitemap --------------------------------------------------------

    def test_el_sitemap_solo_anuncia_las_fichas_de_fase(self):
        """Mismo filtro que el listado (geografia.q_fase): fuera de
        fase no se anuncia; esas fichas se llegan por enlace y ya
        llevan noindex."""
        response = self._get('/sitemap.xml')
        xml = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response['Content-Type'].startswith('application/xml'))
        sitio = settings.SITIO_URL.rstrip('/')
        self.assertIn('<loc>%s/</loc>' % sitio, xml)
        self.assertIn('/business/%s' % self.en_fase.slug, xml)
        self.assertNotIn(self.fuera.slug, xml)
        self.assertNotIn(self.sin_publicar.slug, xml)
        self.assertIn('<lastmod>', xml)

    # --- PWA minima (auditoria E) ---------------------------------------

    def test_el_manifest_se_sirve_con_su_tipo(self):
        """Sin application/manifest+json el navegador rechaza el
        manifest y no instala nada — mimetypes no trae .webmanifest en
        todos los sistemas, asi que serve_react lo declara a mano."""
        manifiesto = self.build / 'manifest.webmanifest'
        manifiesto.write_text('{"name": "BuscandoAndo"}', encoding='utf-8')
        self.addCleanup(manifiesto.unlink, missing_ok=True)

        respuesta = self._get('/manifest.webmanifest')
        # Windows no deja borrar un fichero con el handle abierto
        # (FileResponse lo mantiene): cerrar la respuesta va ANTES de
        # borrar, que es como se ejecutan las cleanups (LIFO).
        self.addCleanup(respuesta.close)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta['Content-Type'], 'application/manifest+json')


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class FrenoLoginAdminTests(TestCase):
    """El freno de intentos contra /admin/login/ (auditoria 19/oct).

    Un ataque de diccionario no puede probar contrasenas sin limite:
    5 fallos por IP y 25 por usuario, y cuando salta, 429 sin siquiera
    mirar la contrasena.
    """

    CLAVE_BUENA = 'clave-correcta-12345'
    URL = '/admin/login/'

    def setUp(self):
        cache.clear()
        get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', self.CLAVE_BUENA)

    def _post(self, clave='equivocada', ip='127.0.0.1', usuario='admin'):
        return self.client.post(self.URL, {
            'username': usuario,
            'password': clave,
            'next': '/admin/',
        }, REMOTE_ADDR=ip)

    def test_cinco_fallos_y_al_sexto_entra_el_freno(self):
        for _ in range(5):
            # Django pinta el error con 200: eso es lo que cuenta.
            self.assertEqual(self._post().status_code, 200)

        respuesta = self._post(clave=self.CLAVE_BUENA)

        # Ni con la contrasena buena: la contraseña no llega a probarse.
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn('Retry-After', respuesta)

    def test_un_freno_en_una_ip_no_arrstra_a_otra(self):
        for _ in range(5):
            self._post(ip='203.0.113.9')

        respuesta = self._post(clave=self.CLAVE_BUENA, ip='198.51.100.7')

        self.assertEqual(respuesta.status_code, 302)

    def test_el_freno_no_toca_al_formulario(self):
        for _ in range(6):
            self._post()

        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 200)

    def test_un_login_bueno_borra_su_contador(self):
        for _ in range(4):
            self._post()
        self.assertEqual(
            self._post(clave=self.CLAVE_BUENA).status_code, 302)

        for _ in range(4):
            self._post()
        self.assertEqual(
            self._post(clave=self.CLAVE_BUENA).status_code, 302)

    def test_el_freno_de_usuario_no_mira_ips(self):
        """Un ataque que cambia de IP a cada rato acaba en el techo
        de usuario (25), no se libra por cambiar de cubeta."""
        for i in range(25):
            self._post(ip='203.0.113.%d' % (i + 1))

        respuesta = self._post(clave=self.CLAVE_BUENA, ip='198.51.100.7')

        self.assertEqual(respuesta.status_code, 429)

    def test_otros_usuarios_no_arrastran_al_admin(self):
        """Si alguien candade 'otro' 25 veces, el admin sigue entrando."""
        get_user_model().objects.create_user('otro', password='x')
        for i in range(25):
            self._post(usuario='otro', ip='203.0.113.%d' % (i + 1))

        respuesta = self._post(clave=self.CLAVE_BUENA, ip='198.51.100.7')

        self.assertEqual(respuesta.status_code, 302)

    def test_los_intentos_bloqueados_no_alargan_la_espera(self):
        """Quien llega con el freno puesto no suma ni reabre nada:
        el candado se levanta solo cuando expira su ventana."""
        for _ in range(5):
            self._post()
        for _ in range(3):
            self.assertEqual(self._post().status_code, 429)

        # siguen siendo 5: los3 bloqueados no cuentan como fallo
        self.assertEqual(cache.get('ba-login:ip:127.0.0.1'), 5)


class CabecerasCSPTests(TestCase):
    """La politica de seguridad tras el Bloque A (auditoria externa).

    Dos regresiones concretas que ya ocurrieron:

    * unpkg volvia al ``style-src`` aunque el ``leaflet.css`` ya va
      empaquetado (lo importa ``MapView.jsx``);
    * el mapa del admin quedo ROTO en produccion: ``business_admin.js``
      cargaba Leaflet desde unpkg y hacia ``fetch`` a nominatim, y la
      CSP se lo impedía — auto-alojado el primero en
      ``/static/admin/leaflet/`` y declarado el segundo en
      ``connect-src``.
    """

    def _csp(self):
        return self.client.get(URL)['Content-Security-Policy']

    def test_sin_unpkg_en_style_src(self):
        csp = self._csp()
        self.assertNotIn('unpkg', csp)
        self.assertIn("style-src 'self' 'unsafe-inline';", csp)

    def test_geocodificador_del_admin_declarado(self):
        self.assertIn(
            'https://nominatim.openstreetmap.org', self._csp())

    def test_scripts_sigue_solo_self(self):
        self.assertIn("script-src 'self';", self._csp())

    def test_leaflet_del_admin_esta_en_static(self):
        """Los ficheros que business_admin.js pide tienen que existir:
        sin ellos el admin se queda sin mapa otra vez."""
        base = Path(settings.BASE_DIR) / 'static' / 'admin' / 'leaflet'
        for relativo in ('leaflet.js', 'leaflet.css',
                         'images/marker-icon.png',
                         'images/marker-icon-2x.png',
                         'images/marker-shadow.png',
                         'images/layers.png', 'images/layers-2x.png'):
            self.assertTrue(
                (base / relativo).is_file(), 'falta %s' % relativo)


class CabecerasPermisosTests(TestCase):
    """Permissions-Policy (auditoria E, menores).

    La web le pide una sola cosa al navegador: geolocalizacion, y solo
    para si misma (el buscador R1/R3, el mismo motivo que la CSP
    declare nominatim). Todo lo demas se niega por delante: aunque un
    script colado llegara a ejecutarse, no podra tocar camara,
    microfono, pagos ni USB.
    """

    def _permisos(self):
        return self.client.get(URL)['Permissions-Policy']

    def test_deja_la_geolocalizacion_para_si_misma(self):
        self.assertIn('geolocation=(self)', self._permisos())

    def test_apaga_lo_que_la_pagina_no_usa(self):
        permisos = self._permisos()
        for apagado in ('camera=()', 'microphone=()', 'payment=()',
                        'usb=()'):
            with self.subTest(feature=apagado):
                self.assertIn(apagado, permisos)
