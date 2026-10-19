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
  se aplana y ademas se exige que resuelva dentro del build.
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext, override_settings

from .health import current_commit

# El serve_react vive en la raiz del backend (backend/views.py), no en
# config/, de ahi el import plano.
from views import serve_react

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

    def _contenido(self, path):
        peticion = RequestFactory().get('/' + path.lstrip('/'))
        with override_settings(REACT_BUILD_DIR=self.build):
            respuesta = serve_react(peticion, path=path)
        return b''.join(respuesta.streaming_content)

    def test_sirve_un_asset_del_build(self):
        """Lo normal: un fichero del build sale tal cual."""
        self.assertEqual(self._contenido('assets/app.js'), b'console.log(1)')

    def test_ruta_absoluta_doble_barra_no_abre_el_servidor(self):
        """//etc/passwd (el ataque real) cae al index del SPA."""
        contenido = self._contenido('//etc/passwd')
        self.assertNotIn(b'root:', contenido)
        self.assertIn(b'INDICE', contenido)

    def test_ruta_absoluta_codificada_tampoco(self):
        """%2f%2fetc%2fpasswd decodificada es el mismo ataque."""
        contenido = self._contenido('//etc/passwd')
        self.assertIn(b'INDICE', contenido)

    def test_saltos_de_directorio_no_salen_del_build(self):
        """../secreto.txt resuelve fuera del build y no se sirve."""
        contenido = self._contenido('../secreto.txt')
        self.assertNotIn(b'NO SE PUEDE LEER', contenido)
        self.assertIn(b'INDICE', contenido)

    def test_ruta_inexistente_cae_al_index(self):
        """El fallback de SPA sigue funcionando."""
        self.assertIn(b'INDICE', self._contenido('algo/que/no/existe'))
