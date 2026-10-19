"""Lo que hay que proteger de las metricas de uso.

Tres promesas del modulo ``uso`` y una de la integracion con las
vistas:

1. lo que pasa se cuenta UNA vez por dia, no por peticion ni por fila;
2. la plataforma sale de la cabecera del cliente o del User-Agent,
   nunca de nada identificable;
3. si la base no puede escribir, la peticion sigue su camino — un
   contador jamas tumba una busqueda;
4. el listado, la ficha y la correccion cuentan donde tienen que
   contar, y el resumen del admin solo lo ve el admin.
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from business_locations.models import BusinessLocation
from businesses import geografia
from businesses.models import Business, Category, PublicationStatus

from .models import TerminoDia, UsoDiario

BUSINESSES_URL = '/api/businesses/'
CORRECTIONS_URL = '/api/corrections/'

# El admin maquilla las hojas con el storage con manifest, que solo
# resuelve despues de `collectstatic`: en los tests no hay manifest y
# la pagina de admin ni llegaria a pintarse. Mismo tramite que en
# businesses/tests.py (STATIC_SIN_MANIFEST).
STATIC_SIN_MANIFEST = {
    **settings.STORAGES,
    'staticfiles': {'BACKEND':
                    'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

NAVEGADOR = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'


class MetricasDeUsoTests(TestCase):
    """El contador del dia: sin duplicar, sin identificar, sin romper."""

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.category = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.negocio = Business.objects.create(
            name='Cafeteria Central',
            slug='cafeteria-central',
            description='Descripcion de prueba',
            category=cls.category,
            publication_status=cls.publicado,
        )
        moca = geografia.cabecera_para('Moca', 'Espaillat')
        cls.moca = moca
        cls.location = BusinessLocation.objects.create(
            business=cls.negocio,
            municipality='Moca',
            province='Espaillat',
            latitude=moca['lat'],
            longitude=moca['lng'],
        )

    def _consultar(self, **params):
        return self.client.get(BUSINESSES_URL, params,
                               HTTP_USER_AGENT=NAVEGADOR)

    def test_la_consulta_se_cuenta_una_sola_vez_por_dia(self):
        primera = self._consultar(text='cafeteria',
                                  lat=self.moca['lat'], lng=self.moca['lng'])
        self.assertEqual(primera.status_code, 200)

        fila = UsoDiario.objects.get(evento='consulta')
        self.assertEqual(fila.total, 1)
        self.assertEqual(fila.provincia, 'Espaillat')
        self.assertEqual(fila.municipio, 'Moca')

        self._consultar(text='cafeteria',
                        lat=self.moca['lat'], lng=self.moca['lng'])
        self.assertEqual(UsoDiario.objects.filter(evento='consulta').count(), 1)
        fila.refresh_from_db()
        self.assertEqual(fila.total, 2)

    def test_sin_coordenadas_no_hay_lugar(self):
        self._consultar(text='cafeteria')

        fila = UsoDiario.objects.get(evento='consulta')
        self.assertEqual((fila.provincia, fila.municipio), ('', ''))

    def test_la_plataforma_se_declara_o_se_adivina_sin_identificar(self):
        # Con Mozilla y sin cabecera: web.
        self._consultar(text='uno')
        # Sin nada parecido a navegador: otra.
        self.client.get(BUSINESSES_URL, {'text': 'dos'},
                        HTTP_USER_AGENT='curl/8.4.0')
        # El UA del cliente de la app: app.
        self.client.get(BUSINESSES_URL, {'text': 'tres'},
                        HTTP_USER_AGENT='okhttp/4.12.0')
        # La cabecera de la casa manda sobre el UA.
        self.client.get(BUSINESSES_URL, {'text': 'cuatro'},
                        HTTP_USER_AGENT=NAVEGADOR,
                        HTTP_X_PLATAFORMA='app')

        placas = {f.plataforma: f.total
                  for f in UsoDiario.objects.filter(evento='consulta')}
        self.assertEqual(placas, {'web': 1, 'otro': 1, 'app': 2})

    def test_el_termino_se_normaliza_y_los_ceros_se_cuentan(self):
        # Nada parecido a esto: 1 busqueda, 1 sin resultados.
        self._consultar(text='zzzznoexiste')
        # La misma busqueda en otras mayusculas/tildes: misma fila.
        self._consultar(text='CAFETERÍA')
        self._consultar(text='cafeteria')

        cero = TerminoDia.objects.get(termino='zzzznoexiste')
        self.assertEqual((cero.busquedas, cero.sin_resultados), (1, 1))

        ok = TerminoDia.objects.get(termino='cafeteria')
        self.assertEqual((ok.busquedas, ok.sin_resultados), (2, 0))

    def test_abrir_una_ficha_se_cuenta(self):
        respuesta = self.client.get(
            '/api/businesses/cafeteria-central/', HTTP_USER_AGENT=NAVEGADOR)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            UsoDiario.objects.get(evento='ficha').total, 1)

    def test_enviar_una_correccion_se_cuenta(self):
        respuesta = self.client.post(CORRECTIONS_URL, {
            'business': self.negocio.id,
            'campo': 'telefono',
            'mensaje': 'El telefono bueno es 809-555-0000',
        }, HTTP_USER_AGENT=NAVEGADOR)

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(
            UsoDiario.objects.get(evento='correccion').total, 1)

    def test_una_metrica_caida_no_tumba_la_peticion(self):
        """La promesa del modulo: si la base no puede contar, la
        busqueda sigue su camino igual."""
        with mock.patch('uso.models._subir',
                        side_effect=RuntimeError('la base no puede')):
            respuesta = self._consultar(text='cafeteria',
                                        lat=self.moca['lat'],
                                        lng=self.moca['lng'])

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(UsoDiario.objects.count(), 0)


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class ResumenDelAdminTests(TestCase):
    """El resumen: dentro del admin y solo para el admin."""

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            'admin_metricas', 'metricas@example.com', 'clave-para-el-test-9')

    def test_el_resumen_se_ve_logueado_y_redirige_sin_login(self):
        sin_login = self.client.get('/admin/uso/usodiario/resumen/')
        self.assertEqual(sin_login.status_code, 302)

        self.client.force_login(self.admin)
        vacio = self.client.get('/admin/uso/usodiario/resumen/')
        self.assertEqual(vacio.status_code, 200)
        self.assertContains(vacio, 'Todavia no hay datos')

        UsoDiario.objects.create(
            fecha=timezone.localdate(), evento='consulta', total=5)
        con_login = self.client.get('/admin/uso/usodiario/resumen/')

        self.assertEqual(con_login.status_code, 200)
        self.assertContains(con_login, 'Por evento y dia')
        self.assertContains(con_login, 'Consulta al listado')

    def test_el_listado_ofrece_el_resumen(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get('/admin/uso/usodiario/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ver resumen')
