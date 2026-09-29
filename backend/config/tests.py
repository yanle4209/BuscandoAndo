"""Tests del health check de Render (GET /api/health/).

Lo que protegemos aqui NO es solo "que devuelva 200", sino las tres
decisiones de diseno de ``config/health.py``:

* responde sin tocar la BD (para que una BD lenta no reinicie el
  servicio en bucle),
* no se cachea (porque delante hay un CDN),
* expone el SHA del commit (para saber que codigo hay en produccion).
"""

import os
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .health import current_commit

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
