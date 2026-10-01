"""Tests de la API de destacados.

Cubren los dos puntos que usa la app (web y Android):

* ``GET /api/businesses/featured-by-search/`` -> hasta 3 destacados activos
  que coincidan con la busqueda, del mejor nivel al peor.
* ``GET /api/businesses/?featured=true``     -> destacados ordenados por nivel.

Historial: ambos endpoints filtraban por ``'large'/'medium'/'small'`` (tiers
heredados), pero ``Business.FEATURED_TIERS`` solo admite ``'1'..'4'``. Por eso
la web llamaba a ``featured-by-search`` y siempre recibia ``[]``.
"""
import datetime
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from . import geografia, osm, validacion
from .levantamiento import LIMITE_ENVIOS_POR_MINUTO
from .models import Business, Correction, Colaborador, Envio

BUSINESSES_URL = '/api/businesses/'
FEATURED_BY_SEARCH_URL = '/api/businesses/featured-by-search/'
CORRECTIONS_URL = '/api/corrections/'
CABECERAS_URL = '/api/cabeceras/'
PENDIENTES_URL = '/api/pendientes/'
LEVANTAMIENTO_URL = '/api/levantamiento/'


class CorrectionApiTests(TestCase):
    """Formulario "Corregir" del frontend.

    Tres reglas que hay que proteger:

    1. cualquiera puede CREAR un aviso (es un formulario abierto, sin login);
    2. solo staff puede LEER la lista. Esto es lo delicado: el
       DEFAULT_PERMISSION_CLASSES del proyecto es AllowAny, asi que sin el
       override de CorrectionViewSet los avisos de unos usuarios saldrian
       publicos para todos junto con las notas internas del admin;
    3. quien avisa no puede fijarse su propio estado.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.category = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')
        cls.business = Business.objects.create(
            name='Cafeteria Central',
            description='Descripcion de prueba',
            category=cls.category,
            publication_status=cls.publicado,
            operational_status=cls.op_status,
        )

    def post(self, **extra):
        """POST en JSON, igual que lo hace axios desde el frontend."""
        payload = {
            'business': self.business.id,
            'campo': 'telefono',
            'mensaje': 'El telefono bueno es 809-555-0000.',
        }
        payload.update(extra)
        return self.client.post(
            CORRECTIONS_URL, payload, content_type='application/json'
        )

    # ------------------------- creacion publica -------------------------
    def test_un_visitante_sin_login_puede_enviar_un_aviso(self):
        response = self.post()

        self.assertEqual(response.status_code, 201, response.data)
        correccion = self.business.corrections.get()
        self.assertEqual(correccion.campo, 'telefono')
        self.assertEqual(correccion.estado, 'pendiente')

    def test_acepta_un_aviso_por_cada_dato_de_la_tarjeta(self):
        """El formulario deja elegir todos los campos de la tarjeta."""
        for campo, _label in Correction.CAMPOS:
            response = self.post(campo=campo)
            self.assertEqual(response.status_code, 201, response.data)

        self.assertEqual(self.business.corrections.count(), len(Correction.CAMPOS))

    # --------------------------- validacion ----------------------------
    def test_un_mensaje_muy_corto_se_rechaza(self):
        response = self.post(mensaje='mal')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.business.corrections.count(), 0)

    def test_un_campo_inventado_se_rechaza(self):
        response = self.post(campo='dni')

        self.assertEqual(response.status_code, 400)

    def test_un_negocio_que_no_existe_se_rechaza(self):
        response = self.post(business=999999)

        self.assertEqual(response.status_code, 400)

    def test_quien_avisa_no_puede_fijar_su_estado(self):
        """estado y nota_admin ni entran en CreateSerializer."""
        response = self.post(estado='aplicada', nota_admin='borrame esto')

        self.assertEqual(response.status_code, 201, response.data)
        correccion = self.business.corrections.get()
        self.assertEqual(correccion.estado, 'pendiente')
        self.assertEqual(correccion.nota_admin, '')

    # ------------------------ lectura solo staff ------------------------
    def test_la_lista_no_es_publica(self):
        self.post()

        response = self.client.get(CORRECTIONS_URL)

        self.assertIn(
            response.status_code, (401, 403),
            'El listado de avisos se esta colando en publico',
        )

    def test_el_admin_si_puede_leer_la_lista(self):
        self.post()
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        response = self.client.get(CORRECTIONS_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_el_formulario_funciona_con_el_admin_abierto_en_el_mismo_dominio(self):
        """Regresion del CSRF.

        DRF autentica por sesion por defecto: si el visitante tiene la
        sesion del admin abierta en el mismo dominio, SessionAuthentication
        le exige token CSRF y el formulario devolveria 403. Por eso el
        action create va con authentication_classes = []. Este test es el
        que falla si alguien lo quita.
        """
        # enforce_csrf_checks=True porque el cliente de pruebas se salta
        # la validacion de CSRF POR DEFECTO: sin el, el test pasaria
        # tambien con el codigo roto y no serviria de nada.
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        User = get_user_model()
        client.force_login(
            User.objects.create_superuser('admin2', 'admin2@example.com', 'x')
        )

        response = client.post(
            CORRECTIONS_URL,
            {
                'business': self.business.id,
                'campo': 'horario',
                'mensaje': 'Cierra a las 6 de la tarde, no a las 8.',
            },
            content_type='application/json',
        )

        self.assertEqual(
            response.status_code, 201,
            f'El publico no puede enviar con la sesion del admin abierta: {response.data}',
        )


class FeaturedApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.borrador = PublicationStatus.objects.create(name='Borrador', slug='borrador')
        cls.category = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')

    def make_business(self, name, tier=None, *, featured=True, publication_status=None):
        """Crea un negocio ya destacado (o no) y lo devuelve."""
        return Business.objects.create(
            name=name,
            description=f'Descripcion de {name}',
            short_description=name,
            category=self.category,
            publication_status=publication_status or self.publicado,
            operational_status=self.op_status,
            is_featured=featured,
            featured_tier=tier,
            featured_permanent=featured,
        )

    # ------------------------------------------------------------------
    # GET /api/businesses/featured-by-search/
    # ------------------------------------------------------------------
    def test_featured_by_search_usa_los_tiers_nuevos(self):
        """Los tiers '1'..'4' deben encontrar; los antiguos 'large' no."""
        for tier in ['4', '3', '2', '1']:
            self.make_business(f'Negocio Nivel {tier}', tier)

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'Negocio'}).json()

        self.assertEqual([b['featured_tier'] for b in data], ['1', '2', '3'])

    def test_featured_by_search_devuelve_como_maximo_tres(self):
        for tier in ['1', '2', '3', '4']:
            self.make_business(f'Negocio Nivel {tier}', tier)

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'Negocio'}).json()

        self.assertEqual(len(data), 3)
        self.assertNotIn('4', [b['featured_tier'] for b in data])

    def test_featured_by_search_sin_filtros_devuelve_vacio(self):
        """Sin texto/ciudad/categoria no hay criterio de busqueda -> []."""
        self.make_business('Negocio Sin Filtro', '1')

        self.assertEqual(self.client.get(FEATURED_BY_SEARCH_URL).json(), [])

    def test_featured_by_search_ignora_no_destacados(self):
        """Un negocio con tier pero sin is_featured no es destacado."""
        self.make_business('Negocio Comun', '1', featured=False)

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'Negocio'}).json()

        self.assertEqual(data, [])

    def test_featured_by_search_ignora_expirados(self):
        """El destacado caducado no debe salir ni aqui ni en la lista."""
        start = timezone.now() - datetime.timedelta(weeks=3)
        biz = self.make_business('Negocio Caducado', '1')
        biz.featured_permanent = False
        biz.featured_weeks = 1
        biz.featured_start_date = start
        biz.featured_end_date = start + datetime.timedelta(weeks=1)
        biz.save()

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'Negocio'}).json()

        self.assertEqual(data, [])

    def test_featured_by_search_solo_negocios_publicados(self):
        self.make_business('Negocio Borrador', '1', publication_status=self.borrador)

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'Negocio'}).json()

        self.assertEqual(data, [])

    # ------------------------------------------------------------------
    # GET /api/businesses/?featured=true
    # ------------------------------------------------------------------
    def test_featured_true_ordenado_por_nivel(self):
        """Debe ordenar 1,2,3,4 y no caer en Meta.ordering ('-created_at')."""
        for tier in ['4', '1', '3', '2']:
            self.make_business(f'Negocio Nivel {tier}', tier)

        response = self.client.get(BUSINESSES_URL, {'featured': 'true'})
        data = response.json()

        self.assertEqual(data['count'], 4)
        self.assertEqual(
            [b['featured_tier'] for b in data['results']],
            ['1', '2', '3', '4'],
        )

    def test_featured_true_sin_nivel_va_ultimo(self):
        self.make_business('Negocio Nivel 1', '1')
        self.make_business('Negocio Sin Nivel', None)

        data = self.client.get(BUSINESSES_URL, {'featured': 'true'}).json()

        self.assertEqual(
            [b['featured_tier'] for b in data['results']],
            ['1', None],
        )

    def test_featured_true_excluye_no_destacados(self):
        self.make_business('Destacado', '1')
        self.make_business('Normal', None, featured=False)

        data = self.client.get(BUSINESSES_URL, {'featured': 'true'}).json()

        self.assertEqual(data['count'], 1)


# Cabecera de Moca: el mismo punto con el que se midio la cobertura en
# produccion (131 fichas a 5 km, 322 a 10 km, 325 en total).
MOCA_LAT = 19.3964
MOCA_LNG = -70.5274


class RadioDeBusquedaTests(TestCase):
    """R1: las busquedas son unica y exclusivamente a 5 km del punto activo.

    Tres negocios a la misma longitud que Moca y a tres distancias
    distintas, para poder afirmar sin ambiguedad que el corte es en 5 y no
    en 10 (que era el default anterior):

    * Cerca  19.4000 -> ~0.40 km
    * Medio  19.4100 -> ~1.51 km
    * Lejos  19.4500 -> ~5.97 km
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.category = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')

    def make_business(self, name, lat, lng, *, tier=None, featured=True):
        biz = Business.objects.create(
            name=name,
            description=f'Descripcion de {name}',
            short_description=name,
            category=self.category,
            publication_status=self.publicado,
            operational_status=self.op_status,
            is_featured=featured,
            featured_tier=tier,
            featured_permanent=featured,
        )
        BusinessLocation.objects.create(business=biz, latitude=lat, longitude=lng)
        return biz

    def setUp(self):
        self.make_business('Cerca', 19.4000, MOCA_LNG, featured=False)
        self.make_business('Medio', 19.4100, MOCA_LNG, featured=False)
        self.make_business('Lejos', 19.4500, MOCA_LNG, featured=False)

    def nombres(self, **params):
        params.setdefault('lat', MOCA_LAT)
        params.setdefault('lng', MOCA_LNG)
        data = self.client.get(BUSINESSES_URL, params).json()
        return sorted(b['name'] for b in data['results'])

    def test_sin_radius_el_defecto_es_5_km_no_10(self):
        """El default anterior era 10 y meteria 'Lejos' (~6 km)."""
        self.assertEqual(self.nombres(), ['Cerca', 'Medio'])

    def test_un_radius_mayor_no_amplia_el_circulo(self):
        """R1.3: el radio es fijo en 5 km en las dos plataformas."""
        self.assertEqual(self.nombres(radius=20), ['Cerca', 'Medio'])

    def test_un_radius_mas_pequeno_si_se_respeta(self):
        """Poder pedir menos si: el tope es el maximo, no el valor unico."""
        self.assertEqual(self.nombres(radius=1), ['Cerca'])

    def test_radius_basura_no_devuelve_500(self):
        """Regresion: float('abc') revientaba el endpoint."""
        response = self.client.get(
            BUSINESSES_URL, {'lat': MOCA_LAT, 'lng': MOCA_LNG, 'radius': 'abc'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(b['name'] for b in response.json()['results']),
            ['Cerca', 'Medio'],
        )

    def test_sin_coordinadas_no_se_recorta(self):
        """Sin punto activo no hay radio que aplicar (R1.1: no deberia
        ocurrir, porque el frontend no consulta sin punto, pero no debe
        romper)."""
        response = self.client.get(BUSINESSES_URL, {'radius': 'abc'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 3)

    def test_featured_by_search_tambien_filtra_por_radio(self):
        """R1.2: los destacados del buscador entran en el mismo filtro."""
        self.make_business('Destacado Cerca', 19.4000, MOCA_LNG, tier='1')
        self.make_business('Destacado Lejos', 19.4500, MOCA_LNG, tier='2')

        data = self.client.get(FEATURED_BY_SEARCH_URL, {
            'text': 'Destacado', 'lat': MOCA_LAT, 'lng': MOCA_LNG,
        }).json()

        self.assertEqual([b['name'] for b in data], ['Destacado Cerca'])

    def test_featured_by_search_sin_coordinadas_no_se_recorta(self):
        """Sin lat/lng el endpoint se comporta como siempre."""
        self.make_business('Destacado Cerca', 19.4000, MOCA_LNG, tier='1')
        self.make_business('Destacado Lejos', 19.4500, MOCA_LNG, tier='2')

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'Destacado'}).json()

        self.assertEqual(len(data), 2)

    def test_featured_by_search_sigue_vacio_sin_criterio(self):
        """El lat/lng es un recorte adicional, no un criterio de busqueda."""
        self.make_business('Destacado Cerca', 19.4000, MOCA_LNG, tier='1')

        data = self.client.get(
            FEATURED_BY_SEARCH_URL, {'lat': MOCA_LAT, 'lng': MOCA_LNG}
        ).json()

        self.assertEqual(data, [])


class BusquedaPorTextoTests(TestCase):
    """Listado y destacados tienen que casar con el mismo texto.

    En produccion "restaurante" devolvia 0 resultados debajo y 2
    destacados arriba: el listado buscaba en nombre/descripcion y el de
    destacados anadia el nombre de la categoria. El usuario veia
    "Destacados para esta buscar..." sobre "0 resultados", que es lo
    contrario de que siempre haya resultados si estan disponibles.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.categoria = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')

    def make_business(self, name, *, featured, tier=None):
        """Ni el nombre ni la descripcion contienen 'restaurante': solo la categoria."""
        return Business.objects.create(
            name=name,
            description=f'Descripcion de {name}',
            short_description=name,
            category=self.categoria,
            publication_status=self.publicado,
            operational_status=self.op_status,
            is_featured=featured,
            featured_tier=tier,
            featured_permanent=featured,
        )

    def abajo(self, **params):
        data = self.client.get(BUSINESSES_URL, params).json()
        return {b['name'] for b in data['results']}

    def arriba(self, **params):
        return {b['name'] for b in self.client.get(FEATURED_BY_SEARCH_URL, params).json()}

    def test_el_listado_encuentra_por_nombre_de_categoria(self):
        """'restaurante' no esta en el nombre: solo en 'Restaurantes'."""
        self.make_business('Cocina Dona Rosa', featured=False)

        data = self.client.get(BUSINESSES_URL, {'text': 'restaurante'}).json()

        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'Cocina Dona Rosa')

    def test_listado_y_destacados_no_se_contradicen(self):
        """Lo que arriba es un subconjunto de lo de abajo, nunca al reves."""
        self.make_business('Cocina Dona Rosa', featured=True, tier='2')
        self.make_business('Comedor El Parque', featured=True, tier='3')

        abajo = self.abajo(text='restaurante')
        arriba = self.arriba(text='restaurante')

        self.assertTrue(arriba, 'los destacados si encontraban')
        self.assertTrue(
            arriba <= abajo,
            f'los destacados enseñan {sorted(arriba - abajo)} que el listado no ve',
        )

    def test_una_categoria_que_no_coincide_no_inventa_resultados(self):
        """Buscar 'restaurante' no debe traer negocios de otra categoria."""
        self.make_business('Cocina Dona Rosa', featured=False)
        otra = Category.objects.create(name='Farmacias', slug='farmacias')
        Business.objects.create(
            name='Farmacia Central',
            description='Medicinas',
            short_description='Medicinas',
            category=otra,
            publication_status=self.publicado,
            operational_status=self.op_status,
        )

        self.assertEqual(self.abajo(text='restaurante'), {'Cocina Dona Rosa'})


class FiltroCityTests(TestCase):
    """R3.5: `city` dejo de ser filtro por nombre.

    La ciudad ahora son coordenadas + 5 km. Si alguien sigue mandando
    `city=Moca` (cliente con el JS cacheado) el parametro se ignora:
    recortar por nombre seria un segundo radio encubierto, con un tamano
    distinto en cada municipio.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.categoria = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')

    def make_business(self, name, municipio, *, featured=False, tier='2'):
        biz = Business.objects.create(
            name=name,
            description=f'Descripcion de {name}',
            short_description=name,
            category=self.categoria,
            publication_status=self.publicado,
            operational_status=self.op_status,
            is_featured=featured,
            featured_tier=tier if featured else None,
            featured_permanent=featured,
        )
        BusinessLocation.objects.create(
            business=biz,
            municipality=municipio,
            latitude=MOCA_LAT,
            longitude=MOCA_LNG,
        )
        return biz

    def test_el_listado_ignora_city(self):
        self.make_business('De Moca', 'Moca')
        self.make_business('De Santiago', 'Santiago')

        data = self.client.get(BUSINESSES_URL, {'city': 'Moca'}).json()

        self.assertEqual(data['count'], 2, 'city no debe recortar nada')

    def test_los_destacados_tambien_lo_ignoran(self):
        # Niveles distintos: featured-by-search coge UNO por nivel
        # (`.first()` dentro de cada tier), asi que dos en el mismo
        # solo dejarian ver uno y el test no estaria mirando `city`.
        self.make_business('De Moca', 'Moca', featured=True, tier='2')
        self.make_business('De Santiago', 'Santiago', featured=True, tier='3')

        data = self.client.get(
            FEATURED_BY_SEARCH_URL, {'city': 'Moca', 'text': 'De '}
        ).json()

        self.assertEqual(
            sorted(b['name'] for b in data),
            ['De Moca', 'De Santiago'],
        )

    def test_por_nivel_se_coge_solo_uno(self):
        """Dos nivel 2 -> solo sale uno; la mezcla es de niveles, no de filas."""
        self.make_business('De Moca', 'Moca', featured=True, tier='2')
        self.make_business('De Santiago', 'Santiago', featured=True, tier='2')

        data = self.client.get(FEATURED_BY_SEARCH_URL, {'text': 'De '}).json()

        self.assertEqual(len(data), 1)

    def test_sin_criterio_sigue_devolviendo_vacio(self):
        """Quitar `city` no rompe la regla de que sin criterio no haya nada."""
        self.make_business('De Moca', 'Moca', featured=True)

        self.assertEqual(self.client.get(FEATURED_BY_SEARCH_URL).json(), [])


class CabecerasApiTests(TestCase):
    """GET /api/cabeceras/ -> las cabeceras municipales del pais (R3).

    Es el dato que hace que el sistema funcione en los 158 municipios y no
    solo donde hay fichas cargadas: ancla del circulo de 5 km cuando no hay
    GPS y fuente del selector manual.
    """

    def cabeceras(self):
        response = self.client.get(CABECERAS_URL)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_es_publico_y_cubre_casi_todo_el_pais(self):
        data = self.cabeceras()

        # 158 municipios en el CSV; el corte se deja holgado para que un
        # anadido futuro no rompa el test.
        self.assertGreaterEqual(len(data), 150)

    def test_toda_cabecera_es_un_punto_usable(self):
        """Ninguna fila puede venirse abajo: sin municipio, sin provincia o
        con coordenadas fuera de la Republica Dominicana inutilizan el
        selector y el ancla del radio."""
        for cab in self.cabeceras():
            with self.subTest(municipio=cab['municipio']):
                self.assertTrue(cab['municipio'].strip())
                self.assertTrue(cab['provincia'].strip())
                self.assertTrue(-72.5 <= cab['lng'] <= -68.0, cab)
                self.assertTrue(17.0 <= cab['lat'] <= 20.5, cab)

    def test_incluye_la_cabecera_de_moca(self):
        """La cabecera con la que se midio la cobertura en produccion."""
        moca = [c for c in self.cabeceras() if c['municipio'] == 'Moca']

        self.assertEqual(len(moca), 1)
        self.assertEqual(moca[0]['provincia'], 'Espaillat')


class ReportePendientesTests(TestCase):
    """GET /api/pendientes/ -> reporte de pendientes por municipio (§11.1).

    La ficha de trabajo con la que se edita y publica a mano lo que no
    llego a cumplir el trio. Hay que proteger tres cosas:

    1. que **solo staff** la lea — dentro estan fichas sin publicar y el
       reparto de trabajo, y el DEFAULT_PERMISSION_CLASSES del proyecto es
       AllowAny;
    2. que agrupe por campo faltante **y marque el trio**: lo que sale de
       aqui es lo que un editor va a ir rellenando, y el trio es lo que
       decide si una ficha se publica sola;
    3. que traiga **cabecera y radio**, que es lo que ancla el circulo de
       5 km con el que se mide si una ficha entrara en el municipio.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.en_revision = PublicationStatus.objects.create(name='En Revision', slug='en-revision')
        cls.category = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')

        # Nada que pedir: no debe salir ni en el contador ni en la lista.
        cls.completa = cls.crear(
            'La Receta', telefono='809-555-1111', extras=True, horario=True,
        )
        # Cumple el trio, pero no horario ni contacto extra: se publica
        # sola y aun asi sigue siendo un pendiente para quien edita.
        cls.sin_extras = cls.crear('Panaderia Sol', telefono='809-555-2222')
        # Sin telefono no hay trio -> queda en revision.
        cls.sin_telefono = cls.crear(
            'Taller El Rayo', telefono='', estado=cls.en_revision,
            procedencia='importado',
        )
        # Con fila de ubicacion pero sin coordenadas: sigue en Moca y aun
        # asi no tiene punto.
        cls.sin_coordenadas = cls.crear(
            'Kiosko La Esquina', lat=None, lng=None, calle='',
            estado=cls.en_revision,
        )
        # Ni siquiera dice a que municipio pertenece.
        cls.sin_ubicacion = cls.crear(
            'Puesto Ambulante', con_ubicacion=False, estado=cls.en_revision,
        )
        # Otro municipio: no debe colarse en el de Moca.
        cls.en_santiago = cls.crear(
            'Cafe Santiago', municipio='Santiago', provincia='Santiago',
            lat=19.4500, lng=-70.6900,
        )
        # Nombre sin acento en la base, con acento en el CSV.
        cls.en_bani = cls.crear(
            'Fonda Bani', municipio='Bani', provincia='Peravia',
            lat=18.2793, lng=-70.3330,
        )

    @classmethod
    def crear(cls, nombre, *, municipio='Moca', provincia='Espaillat',
              lat=MOCA_LAT, lng=MOCA_LNG, calle='Calle 1',
              telefono='809-555-0000', extras=False, estado=None,
              procedencia='manual', horario=False, con_ubicacion=True):
        biz = Business.objects.create(
            name=nombre,
            description='Descripcion de %s' % nombre,
            category=cls.category,
            publication_status=estado or cls.publicado,
            operational_status=cls.op_status,
            procedencia=procedencia,
        )
        if con_ubicacion:
            BusinessLocation.objects.create(
                business=biz, street=calle, municipality=municipio,
                province=provincia, latitude=lat, longitude=lng,
            )
        if telefono:
            contact = {'phone': telefono}
            if extras:
                contact = {
                    'phone': telefono,
                    'whatsapp': '+18095550000',
                    'email': 'hola@example.com',
                    'website': 'https://example.com',
                }
            BusinessContact.objects.create(business=biz, **contact)
        if horario:
            BusinessHours.objects.create(
                business=biz, day='Lunes',
                open_time=datetime.time(8, 0),
                close_time=datetime.time(17, 0),
            )
        return biz

    # ------------------------------ acceso ------------------------------
    def test_el_reporte_no_es_publico(self):
        """Dentro se ven fichas sin publicar: no puede ser anonimo."""
        response = self.client.get(PENDIENTES_URL)

        self.assertIn(
            response.status_code, (401, 403),
            'El reporte de pendientes se esta colando en publico',
        )

    def test_un_admin_si_puede_leerlo(self):
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        response = self.client.get(PENDIENTES_URL)

        self.assertEqual(response.status_code, 200)

    # --------------------------- sin municipio --------------------------
    def test_sin_municipio_lista_donde_hay_trabajo(self):
        """La pantalla de entrada: que municipios tienen fichas y cuantas
        le falta algo, para elegir donde se empieza."""
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        datos = self.client.get(PENDIENTES_URL).json()

        por_nombre = {f['municipio']: f for f in datos}
        self.assertEqual(por_nombre['Moca']['total'], 4)
        self.assertEqual(por_nombre['Santiago']['total'], 1)
        # 'La Receta' no le falta nada, las otras tres de Moca si.
        self.assertEqual(por_nombre['Moca']['con_pendientes'], 3)
        # Dos de Moca y la sin municipio esperan publicacion.
        self.assertEqual(por_nombre['Moca']['en_revision'], 2)

    def test_las_fichas_sin_municipio_no_desaparecen(self):
        """No se pueden editar si ni siquiera se sabe donde caen, asi que
        van en su propio casillero en vez de quedar escondidas."""
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        datos = self.client.get(PENDIENTES_URL).json()
        por_nombre = {f['municipio']: f for f in datos}

        self.assertIn('(sin municipio)', por_nombre)
        self.assertEqual(por_nombre['(sin municipio)']['total'], 1)

    # ----------------------------- municipio ----------------------------
    def loguear_admin(self):
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

    def admin(self):
        self.loguear_admin()
        return self.client.get(PENDIENTES_URL, {'municipio': 'Moca'}).json()

    def test_un_municipio_con_fichas_trae_cabecera_y_radio(self):
        """La cabecera ancla el circulo: sin ella no se sabe si una ficha
        nueva entraria en este municipio (R1, DISENO.md 9)."""
        datos = self.admin()

        self.assertEqual(datos['municipio'], 'Moca')
        self.assertEqual(datos['provincia'], 'Espaillat')
        self.assertAlmostEqual(datos['cabecera']['lat'], 19.3964, places=4)
        self.assertAlmostEqual(datos['cabecera']['lng'], -70.5274, places=4)
        self.assertEqual(datos['radio_km'], 5)

    def test_no_contamina_a_otro_municipio(self):
        nombres = [f['nombre'] for f in self.admin()['fichas']]

        self.assertNotIn('Cafe Santiago', nombres)
        self.assertNotIn('Fonda Bani', nombres)

    def test_una_ficha_completa_no_es_pendiente(self):
        datos = self.admin()

        self.assertEqual(datos['total'], 4)
        self.assertEqual(datos['con_pendientes'], 3)
        self.assertNotIn('La Receta', [f['nombre'] for f in datos['fichas']])

    def test_agrupa_por_campo_faltante_y_marca_el_trio(self):
        """§11.1: agrupado por campo. El trio va marcado para que se vea
        de un vistazo que lo que bloquea la publicacion."""
        por_campo = {f['campo']: f for f in self.admin()['por_campo']}

        self.assertTrue(por_campo['telefono']['en_trio'])
        self.assertTrue(por_campo['punto']['en_trio'])
        self.assertFalse(por_campo['horario']['en_trio'])
        self.assertGreaterEqual(por_campo['telefono']['cantidad'], 1)

    def test_el_trio_va_primero_en_la_cola(self):
        """Si no, los campos que no tiene casi nadie (WhatsApp, web)
        taparian el telefono, que es el que decide la publicacion."""
        filas = self.admin()['por_campo']
        nombres = [f['campo'] for f in filas]

        ultimo_trio = max(
            nombres.index(c) for c in ('nombre', 'telefono', 'punto')
            if c in nombres
        )
        primero_sin_trio = min(
            i for i, fila in enumerate(filas) if not fila['en_trio']
        )

        self.assertLess(ultimo_trio, primero_sin_trio)

    def test_las_que_hay_que_publicar_van_primero(self):
        """§11-j: son dos acciones distintas en el admin — publicar la que
        nunca cumplio el trio, completar la que ya se publico."""
        fichas = self.admin()['fichas']

        self.assertEqual(fichas[0]['estado'], 'en-revision')
        self.assertEqual(fichas[-1]['estado'], 'publicado')

    def test_trae_la_procedencia(self):
        """§10: lo que viene del servicio entra marcado."""
        por_nombre = {f['nombre']: f for f in self.admin()['fichas']}

        self.assertEqual(por_nombre['Taller El Rayo']['procedencia'], 'importado')
        self.assertEqual(por_nombre['Panaderia Sol']['procedencia'], 'manual')

    def test_un_municipio_del_padron_sin_fichas_da_ceros(self):
        """§11.1 + lo decidido para los 158: un municipio todavia sin
        importar NO es un error, es el trabajo que falta. El cero es la
        informacion: sin el, el reporte solo contaria lo que ya entra."""
        self.loguear_admin()

        response = self.client.get(PENDIENTES_URL, {'municipio': 'Barahona'})

        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual(datos['total'], 0)
        self.assertEqual(datos['fichas'], [])
        self.assertEqual(datos['por_campo'], [])
        # Aun vacio trae la cabecera: es lo que ancla el circulo de 5 km.
        self.assertIsNotNone(datos['cabecera'])
        self.assertEqual(datos['radio_km'], 5)

    def test_un_nombre_que_no_es_de_ningun_municipio_da_404(self):
        """El 404 se reserva para lo que no es de ningun sitio del país."""
        self.loguear_admin()

        response = self.client.get(
            PENDIENTES_URL, {'municipio': 'Villa Que No Existe'}
        )

        self.assertEqual(response.status_code, 404)

    def test_el_listado_cubre_los_158_municipios(self):
        """La pregunta «dónde falta importar» tiene que poder responderse
        con este listado, y hoy no se podia: solo salian los que ya
        tenian fichas."""
        from . import geografia

        self.loguear_admin()

        datos = self.client.get(PENDIENTES_URL).json()
        por_nombre = {f['municipio'] for f in datos}

        faltan = {
            c['municipio'] for c in geografia.cabeceras()
        } - por_nombre
        self.assertEqual(faltan, set())
        # Y lo que no es de ningun municipio del padron sigue saliendo
        # aparte, sin perderse.
        self.assertIn('(sin municipio)', por_nombre)

    # ---------------------- el colaborador (§11-i) ---------------------
    def colaborador(self, municipio='Moca', activo=True):
        from .models import Colaborador

        return Colaborador.objects.create(
            nombre='Pedro', municipio=municipio, activo=activo,
        )

    def con_token(self, colab, **params):
        return self.client.get(
            PENDIENTES_URL, params,
            headers={'X-Colaborador-Token': colab.token},
        )

    def test_sin_firma_no_se_lee(self):
        response = self.client.get(PENDIENTES_URL)

        self.assertEqual(response.status_code, 403)

    def test_un_token_que_no_es_de_nadie_da_401(self):
        """Distinto de «no mando nada»: este puede arreglarse."""
        response = self.client.get(
            PENDIENTES_URL, headers={'X-Colaborador-Token': 'no-existe'}
        )

        self.assertEqual(response.status_code, 401)

    def test_un_colaborador_bloqueado_no_lee(self):
        colab = self.colaborador()
        colab.activo = False
        colab.save()

        response = self.con_token(colab)

        self.assertEqual(response.status_code, 401)

    def test_al_colaborador_solo_le_sale_su_renglon(self):
        """§11-i: «ni reportes ajenos». Si le saliera la lista entera
        veria de un vistazo todos los municipios del país."""
        datos = self.con_token(self.colaborador('Moca')).json()

        self.assertEqual([f['municipio'] for f in datos], ['Moca'])
        self.assertEqual(datos[0]['total'], 4)
        self.assertEqual(datos[0]['con_pendientes'], 3)

    def test_el_colaborador_puede_leer_su_municipio(self):
        """Y sin distinguir mayusculas: el nombre del token lo teclea el
        admin a su manera y el del reporte viene de texto libre."""
        colab = self.colaborador('mOcA')

        datos = self.con_token(colab, municipio='Moca').json()

        self.assertEqual(datos['municipio'], 'Moca')
        self.assertEqual(datos['total'], 4)

    def test_el_acento_no_le_cierra_la_puerta(self):
        """'Bani' en la base, 'Baní' en el padron: mismo municipio."""
        datos = self.con_token(
            self.colaborador('Bani'), municipio='Baní'
        ).json()

        self.assertEqual(datos['municipio'], 'Bani')

    def test_al_colaborador_no_le_toca_otro_municipio(self):
        response = self.con_token(self.colaborador('Moca'), municipio='Santiago')

        self.assertEqual(response.status_code, 403)
        self.assertIn('otro municipio', response.json()['detail'])

    def test_un_token_sin_municipio_no_tiene_reporte(self):
        """No es culpa suya: es un reparto que todavia no se hizo, y el
        reporte no puede inventarle uno."""
        response = self.con_token(self.colaborador(''))

        self.assertEqual(response.status_code, 400)

    def test_al_colaborador_de_un_municipio_vacio_se_le_ensena_el_cero(self):
        """Su encargo: entrar y ver que todavia no ha entrado nada."""
        datos = self.con_token(
            self.colaborador('Barahona'), municipio='Barahona'
        ).json()

        self.assertEqual(datos['total'], 0)
        self.assertEqual(datos['fichas'], [])

    def test_el_nombre_del_municipio_no_distingue_mayusculas_ni_acentos(self):
        """El nombre de la base es texto libre y el del CSV viene de
        Wikipedia: 'Bani' contra 'Baní' es el mismo municipio."""
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        mayusculas = self.client.get(
            PENDIENTES_URL, {'municipio': 'mOcA'}
        ).json()
        sin_acento = self.client.get(
            PENDIENTES_URL, {'municipio': 'baní'}
        ).json()

        self.assertEqual(mayusculas['municipio'], 'Moca')
        self.assertEqual(sin_acento['municipio'], 'Bani')
        # Y la cabecera del CSV (que si lleva acento) se encuentra igual.
        self.assertIsNotNone(sin_acento['cabecera'])
        self.assertEqual(sin_acento['provincia'], 'Peravia')

    # ---------------------------- el trio (R5) --------------------------
    def test_el_trio_es_nombre_telefono_y_punto(self):
        """§10-f: el telefono es obligatorio porque es el propio trio."""
        from . import pendientes

        self.assertTrue(pendientes.cumple_trio(self.completa))
        self.assertFalse(pendientes.cumple_trio(self.sin_telefono))
        self.assertFalse(pendientes.cumple_trio(self.sin_coordenadas))

    def test_los_extras_no_forman_parte_del_trio(self):
        """§10: horario y WhatsApp son pendientes, pero no impiden
        publicar. 'Panaderia Sol' no tiene ninguno de los dos."""
        from . import pendientes

        self.assertTrue(pendientes.cumple_trio(self.sin_extras))
        self.assertIn('horario', pendientes.faltantes_de(self.sin_extras))


CABECERA_MOCA = {
    'municipio': 'Moca',
    'provincia': 'Espaillat',
    'lat': MOCA_LAT,
    'lng': MOCA_LNG,
}


def nodo(nombre, lat=19.3970, lng=-70.5270, **etiquetas):
    """Un elemento de Overpass con la forma que devuelve ``out center``."""
    return {
        'type': 'node',
        'lat': lat,
        'lon': lng,
        'tags': {'name': nombre, **etiquetas},
    }


class ValidacionDeEntradaTests(TestCase):
    """§11.5: la puerta. Lo mal formado NO entra; lo incompleto SI.

    Esta distincion es la que sostiene R5 entero: si la puerta rechazara
    por no cumplir el trio, los que mas necesitamos (los que no tienen
    telefono) no llegarian nunca al reporte de §11.1.
    """

    def validar(self, **extra):
        datos = {
            'nombre': 'Pan del Dia',
            'telefono': '809-555-1111',
            'lat': 19.3970,
            'lng': -70.5270,
            'municipio': 'Moca',
            'cabecera': CABECERA_MOCA,
        }
        datos.update(extra)
        return validacion.validar(**datos)

    # ------------------------------ lo que SI ---------------------------
    def test_un_dato_completo_pasa(self):
        self.assertEqual(self.validar(), [])

    def test_faltar_el_trio_no_rechaza(self):
        """§10-g: quien no tiene telefono no se descarta, se acumula."""
        self.assertEqual(
            self.validar(nombre='Taller Nuevo', telefono='', lat=None, lng=None),
            [],
        )

    def test_sin_cabecera_no_hay_como_verificarlo(self):
        """Sin padron no se puede decir que las coordenadas caen ahi."""
        motivos = self.validar(cabecera=None)

        self.assertEqual(len(motivos), 1)
        self.assertIn('padron', motivos[0])

    # ------------------------------ lo que NO ---------------------------
    def test_un_nombre_vacio_se_rechaza(self):
        self.assertTrue(self.validar(nombre='   '))

    def test_un_telefono_con_letras_se_rechaza(self):
        motivos = self.validar(telefono='no se sabe')

        self.assertEqual(len(motivos), 1)
        self.assertIn('telefono', motivos[0])

    def test_un_punto_fuera_del_circulo_se_rechaza(self):
        """§10: 'importar lejos del centro no entra en ningun circulo'."""
        motivos = self.validar(lat=19.6000, lng=-70.5274)

        self.assertEqual(len(motivos), 1)
        self.assertIn('fuera del circulo', motivos[0])

    def test_un_punto_a_medias_si_se_rechaza(self):
        """Ni falta el trío (que pasa) ni esta completo (que pasa): esta
        partido, que no es ninguna de las dos."""
        motivos = self.validar(lat=None, lng=-70.5270)

        self.assertEqual(len(motivos), 1)
        self.assertIn('incompletas', motivos[0])

    def test_el_radio_es_5_km_por_defecto(self):
        """R1: el canal de envio no puede admitir a mas de 5 km."""
        motivos = self.validar(lat=19.4400, lng=-70.5274)  # ~4.85 km

        self.assertEqual(motivos, [])

        motivos = self.validar(lat=19.4460, lng=-70.5274)  # ~5.51 km

        self.assertEqual(len(motivos), 1)

    # --------------------------- normalizacion --------------------------
    def test_el_prefijo_tel_de_osm_no_llega_a_la_base(self):
        self.assertEqual(
            validacion.limpiar_telefono('tel:+18095551234'),
            '+18095551234',
        )

    def test_de_varios_telefonos_se_queda_el_primero(self):
        self.assertEqual(
            validacion.limpiar_telefono('809-555-1111;809-555-2222'),
            '809-555-1111',
        )

    def test_un_telefono_con_suficientes_digitos_es_valido(self):
        self.assertTrue(validacion.telefono_valido('8095551234'))
        self.assertTrue(validacion.telefono_valido('+1 (809) 555-1234'))
        self.assertFalse(validacion.telefono_valido('123'))
        self.assertFalse(validacion.telefono_valido(''))

    # ---------------------------- duplicados ----------------------------
    def hacer(self, nombre, lat=19.3970, lng=-70.5270):
        publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado',
        )
        biz = Business.objects.create(
            name=nombre,
            description='Descripcion',
            publication_status=publicado,
        )
        BusinessLocation.objects.create(
            business=biz, municipality='Moca', province='Espaillat',
            latitude=lat, longitude=lng,
        )
        return biz

    def test_el_mismo_nombre_con_distinto_acento_es_un_duplicado(self):
        """§10-d: cruzar antes de publicar, y 'Café' contra 'Cafe' es el
        mismo sitio."""
        existente = self.hacer('Café El Sol')
        indice = validacion.indice_de_nombres([existente])

        encontrado = validacion.duplicado(indice, 'CAFE  EL SOL')

        self.assertEqual(encontrado, existente)

    def test_un_nombre_parecido_en_la_misma_esquina_tambien_es_duplicado(self):
        existente = self.hacer('Panaderia Sol')
        indice = validacion.indice_de_nombres([existente])

        encontrado = validacion.duplicado(
            indice, 'Panaderia Sol (Moca)', 19.3970, -70.5270,
        )

        self.assertEqual(encontrado, existente)

    def test_un_negocio_de_otro_municipio_no_es_un_duplicado(self):
        """El cruce es por municipio: dos 'Farmacia Central' distintas
        pueden existir."""
        existente = self.hacer('Farmacia Central')
        indice = {}  # el cruce se hace sobre el municipio, y este no esta

        self.assertIsNone(validacion.duplicado(indice, 'Farmacia Central'))


class ImportarMunicipioTests(TestCase):
    """``manage.py importar_municipio`` -> R5 en la practica.

    Tres pasos dependen del anterior y hay que protegerlos en ese orden:
    validar ANTES de crear, cruzar ANTES de publicar, y publicar SOLO el
    trio. El cuarto, que no se ve a primera vista: lo creado a mano nunca
    se publica solo (VISION.md).
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado',
        )
        cls.en_revision = PublicationStatus.objects.create(
            name='En Revision', slug='en-revision',
        )
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto',
        )
        cls.cerrado = OperationalStatus.objects.create(
            name='Cerrado', slug='cerrado',
        )

    def importar(self, municipio='Moca'):
        salida = io.StringIO()
        call_command('importar_municipio', municipio, stdout=salida)
        return salida.getvalue()

    def hacer_manual(self, nombre):
        """Una ficha creada a mano y sin publicar, en el circulo de Moca."""
        biz = Business.objects.create(
            name=nombre,
            description='Descripcion',
            publication_status=self.en_revision,
            operational_status=self.abierto,
            procedencia='manual',
        )
        BusinessLocation.objects.create(
            business=biz, street='Calle 1 #10', municipality='Moca',
            province='Espaillat', latitude=19.3970, longitude=-70.5270,
        )
        return biz

    # ---------------------- R5: que se publica --------------------------
    @patch('businesses.osm.consultar')
    def test_publica_la_que_cumple_el_trio(self, consultar):
        consultar.return_value = [
            nodo('Pan del Dia', phone='809-555-1111'),
        ]

        self.importar()

        pan = Business.objects.get(name='Pan del Dia')

        self.assertEqual(pan.publication_status.slug, 'publicado')
        self.assertEqual(pan.procedencia, 'importado')

    @patch('businesses.osm.consultar')
    def test_sin_telefono_queda_en_revision_y_no_se_descarta(self, consultar):
        consultar.return_value = [nodo('Taller Nuevo')]

        self.importar()

        taller = Business.objects.get(name='Taller Nuevo')

        self.assertEqual(taller.publication_status.slug, 'en-revision')
        self.assertEqual(taller.procedencia, 'importado')

    # ------------------ §10-d: cruzar antes de publicar -----------------
    @patch('businesses.osm.consultar')
    def test_un_duplicado_no_crea_una_segunda_ficha(self, consultar):
        existente = self.hacer_manual('Pan del Dia')
        consultar.return_value = [
            nodo('Pan del Dia', phone='809-555-1111'),
        ]

        self.importar()

        self.assertEqual(
            Business.objects.filter(name='Pan del Dia').count(), 1,
        )
        # Y el telefono que trae OSM se le pone a la que ya estaba.
        self.assertEqual(existente.contact.phone, '809-555-1111')

    @patch('businesses.osm.consultar')
    def test_correrlo_dos_veces_no_duplica(self, consultar):
        consultar.return_value = [nodo('Pan del Dia', phone='8095551234')]

        self.importar()
        self.importar()

        self.assertEqual(Business.objects.filter(name='Pan del Dia').count(), 1)

    # ---------------------- §11.5: la puerta ----------------------------
    @patch('businesses.osm.consultar')
    def test_un_nombre_vacio_no_entra(self, consultar):
        consultar.return_value = [nodo(''), nodo('Valido', phone='8095551234')]

        self.importar()

        self.assertEqual(Business.objects.count(), 1)
        self.assertEqual(Business.objects.get().name, 'Valido')

    @patch('businesses.osm.consultar')
    def test_un_punto_fuera_del_circulo_no_entra(self, consultar):
        consultar.return_value = [
            nodo('Lejos', lat=19.6000, lng=-70.5274, phone='8095551234'),
        ]

        self.importar()

        self.assertEqual(Business.objects.count(), 0)

    # --------------------------- el municipio ---------------------------
    @patch('businesses.osm.consultar')
    def test_el_municipio_lo_da_la_cabecera_y_no_las_etiquetas(self, consultar):
        consultar.return_value = [
            nodo('Pan', **{'addr:city': 'Otra Cosa', 'phone': '8095551234'}),
        ]

        self.importar()

        pan = Business.objects.get(name='Pan')

        self.assertEqual(pan.location.municipality, 'Moca')
        self.assertEqual(pan.location.province, 'Espaillat')

    @patch('businesses.osm.consultar')
    def test_un_elemento_sin_red_no_se_con_funde_con_un_municipio_vacio(
        self, consultar,
    ):
        """§11: 'Overpass no contesto' y 'no hay nada' son cosas
        distintas; la primera no deberia parecer un municipio sin datos."""
        consultar.return_value = None

        salida = self.importar()

        self.assertEqual(Business.objects.count(), 0)
        self.assertIn('Overpass no contesto', salida)

    # --------------------- VISION.md: quien publica ---------------------
    @patch('businesses.osm.consultar')
    def test_una_ficha_creada_a_mano_no_se_publica_sola(self, consultar):
        """El cruce le completa el telefono, pero quien publica una ficha
        manual es el admin, no el importador."""
        manual = self.hacer_manual('La Receta')
        consultar.return_value = [
            nodo('La Receta', phone='809-555-1111'),
        ]

        self.importar()

        manual.refresh_from_db()

        self.assertEqual(manual.publication_status.slug, 'en-revision')
        self.assertEqual(manual.contact.phone, '809-555-1111')


class CanalDeEnvioTests(TestCase):
    """POST /api/levantamiento/ -> el canal de envio (§11.5).

    Lo que sostiene el diseño y hay que proteger con mas cuidado es una
    asimetria de dos renglones:

        MAL FORMADO  -> rechazado en la puerta (no queda pendiente de nada)
        FALTA EL TRIO -> pendiente en el reporte (nunca se descarta)

    Si se invirtieran, lo que mas necesitamos —los negocios sin telefono—
    dejaria de llegar al reporte de §11.1. Y lo otro, que sin el token no
    se entra: §11-i dice "no hay acceso, hay envio", y por eso da igual
    que el canal este completo desde el primer dia.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado',
        )
        cls.en_revision = PublicationStatus.objects.create(
            name='En Revision', slug='en-revision',
        )
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto',
        )
        cls.category = Category.objects.create(
            name='Panaderias', slug='panaderias',
        )
        cls.colaborador = Colaborador.objects.create(nombre='Pedro')
        cls.otro = Colaborador.objects.create(nombre='Maria')

    # ------------------------------ utilidades -------------------------
    def cuerpo(self, **extra):
        datos = {
            'nombre': 'Pan del Dia',
            'telefono': '809-555-1111',
            'lat': 19.3970,
            'lng': -70.5270,
            'municipio': 'Moca',
            'calle': 'Calle 1 #10',
            'categoria': 'Panaderias',
        }
        datos.update(extra)
        return datos

    def enviar(self, token=None, cliente=None, **extra):
        """Un POST al canal. ``token=None`` manda el bueno; '' ninguno."""
        if token is None:
            token = self.colaborador.token
        encabezados = {'X-Colaborador-Token': token} if token else {}
        return (cliente or self.client).post(
            LEVANTAMIENTO_URL,
            self.cuerpo(**extra),
            content_type='application/json',
            headers=encabezados,
        )

    def hacer(self, nombre, *, procedencia='manual', estado=None,
              telefono='', lat=19.3970, lng=-70.5270, calle='Calle 1 #10'):
        negocio = Business.objects.create(
            name=nombre,
            description='Descripcion',
            category=self.category,
            publication_status=estado or self.en_revision,
            operational_status=self.abierto,
            procedencia=procedencia,
        )
        BusinessLocation.objects.create(
            business=negocio, street=calle, municipality='Moca',
            province='Espaillat', latitude=lat, longitude=lng,
        )
        if telefono:
            BusinessContact.objects.create(business=negocio, phone=telefono)
        return negocio

    # ---------------------------- §11-i: firma -------------------------
    def test_sin_firma_no_entra(self):
        response = self.enviar(token='')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Business.objects.count(), 0)
        self.assertEqual(Envio.objects.count(), 0)

    def test_un_token_inventado_no_entra(self):
        response = self.enviar(token='no-existe')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Business.objects.count(), 0)

    def test_un_colaborador_bloqueado_no_entra(self):
        self.colaborador.activo = False
        self.colaborador.save()

        response = self.enviar()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Business.objects.count(), 0)

    def test_bloquear_a_uno_no_cierra_el_canal_a_los_demas(self):
        """§11.5: el token firma a UNO. Que se haya equivocado Pedro no es
        motivo para dejar a Maria sin poder levantar nada."""
        self.colaborador.activo = False
        self.colaborador.save()

        response = self.enviar(token=self.otro.token)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['estado'], 'publicado')

    def test_el_token_tambien_se_acepta_como_bearer(self):
        response = self.client.post(
            LEVANTAMIENTO_URL,
            self.cuerpo(),
            content_type='application/json',
            headers={'Authorization': 'Bearer ' + self.colaborador.token},
        )

        self.assertEqual(response.status_code, 201)

    def test_del_canal_solo_se_envia_no_se_lee(self):
        """§11-i: no hay acceso, hay envio. Con la firma en la mano no se
        abre ni una lectura."""
        response = self.client.get(
            LEVANTAMIENTO_URL,
            headers={'X-Colaborador-Token': self.colaborador.token},
        )

        self.assertEqual(response.status_code, 405)

    # ------------------------ 1. la puerta -----------------------------
    def test_un_nombre_vacio_se_rechaza_y_no_deja_nada(self):
        response = self.enviar(nombre='   ')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['estado'], 'rechazado')
        self.assertEqual(Business.objects.count(), 0)
        # Si, ademas, quedara "pendiente", seria mentira: no hay nada que
        # editar, no llego nada.
        self.assertEqual(Envio.objects.get().estado, 'rechazado')

    def test_un_telefono_con_letras_se_rechaza(self):
        response = self.enviar(telefono='no se sabe')

        self.assertEqual(response.status_code, 400)
        self.assertIn('telefono', ' '.join(response.data['motivos']).lower())
        self.assertEqual(Business.objects.count(), 0)

    def test_fuera_del_circulo_de_5_km_se_rechaza(self):
        """R1/§10-j: el canal no puede ensanchar el radio."""
        response = self.enviar(lat=19.6000)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Business.objects.count(), 0)

    def test_un_municipio_desconocido_se_rechaza(self):
        response = self.enviar(municipio='Villa Que No Existe')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Business.objects.count(), 0)

    def test_una_coordenada_rota_se_rechaza_como_rota_no_como_faltante(self):
        """La diferencia que mas importa de la puerta.

        ``lat='abc'`` **vino** y viene roto -> se rechaza. Si se
        convirtiera a ``None`` pasaria por "falta el punto" (que se
        perdona) y el error quedaria escondido en un reporte donde nadie
        mira coordenadas.
        """
        response = self.enviar(lat='abc')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Business.objects.count(), 0)
        self.assertIn('numero', ' '.join(response.data['motivos']).lower())

    # --------------------------- 3. el trio ----------------------------
    def test_lo_completo_se_publica_al_momento(self):
        response = self.enviar()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['estado'], 'publicado')
        negocio = Business.objects.get()
        self.assertEqual(negocio.publication_status.slug, 'publicado')
        # Es del canal, no de OSM: lo que distingue "levantado".
        self.assertEqual(negocio.procedencia, 'levantado')

    def test_sin_telefono_queda_pendiente_y_no_se_descarta(self):
        """§10-g: el negocio sin telefono es el que mas queremos en el
        reporte, no el que queremos fuera."""
        response = self.enviar(telefono='')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['estado'], 'pendiente')
        self.assertIn('telefono', response.data['faltan'])
        self.assertEqual(
            Business.objects.get().publication_status.slug, 'en-revision',
        )

    def test_sin_punto_queda_pendiente(self):
        """Falta el trio, no esta roto: tambien entra."""
        response = self.enviar(lat=None, lng=None)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['estado'], 'pendiente')
        self.assertIn('punto', response.data['faltan'])

    def test_una_categoria_desconocida_no_se_crea_desde_aqui(self):
        """Aqui teclea una persona: una errata no debe abrirle una
        categoria nueva al sistema. El importador si la crea, porque el
        nombre viene de OSM y es de fiar."""
        response = self.enviar(categoria='Pan (con errata)')

        self.assertFalse(Category.objects.filter(name='Pan (con errata)').exists())
        # Y no por eso se le retiene: la categoria no es el trio.
        self.assertEqual(response.data['estado'], 'publicado')
        self.assertIn('categoria', response.data['faltan'])

    def test_un_pendiente_del_canal_aparece_en_el_reporte(self):
        """El circuito cerrado: entra por el canal y sale por §11.1."""
        self.enviar(telefono='')
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        response = self.client.get(PENDIENTES_URL, {'municipio': 'Moca'})

        self.assertEqual(response.status_code, 200)
        por_nombre = {f['nombre']: f for f in response.data['fichas']}
        self.assertEqual(por_nombre['Pan del Dia']['estado'], 'en-revision')

    # ------------------------- 2. el cruce -----------------------------
    def test_un_duplicado_no_crea_una_segunda_ficha(self):
        existente = self.hacer('Pan del Dia')

        response = self.enviar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], 'duplicado')
        self.assertEqual(
            Business.objects.filter(name='Pan del Dia').count(), 1,
        )
        self.assertEqual(existente.contact.phone, '809-555-1111')

    def test_completarle_el_trio_a_una_importada_la_publica(self):
        """§10-d + §10-f, juntas.

        La ficha existente es una importada sin telefono; el envio trae el
        que nos falta. Se le completa **y** se publica, porque ya cumple
        el trio. Es la prueba de que hay que releer la instancia: si no,
        `cumple_trio` veria la cache de "no tiene contacto" de antes de
        crearlo y la ficha se quedaria en revision.
        """
        existente = self.hacer('Pan del Dia', procedencia='importado')

        response = self.enviar()

        self.assertEqual(response.data['estado'], 'duplicado')
        # `enriquecer` informa el objeto que toco, y al no existir contacto
        # lo que crea y anota es 'contacto' (que es donde vive el telefono).
        self.assertIn('contacto', response.data['completado'])
        existente.refresh_from_db()
        self.assertEqual(existente.publication_status.slug, 'publicado')
        self.assertEqual(existente.contact.phone, '809-555-1111')

    def test_lo_manual_no_se_publica_sola_aunque_lo_completen(self):
        """VISION.md: quien publica una ficha hecha a mano es el admin,
        aun cuando el cruce le meta el telefono."""
        self.hacer('Pan del Dia', procedencia='manual')

        response = self.enviar()

        self.assertEqual(response.data['estado'], 'duplicado')
        self.assertEqual(
            Business.objects.get().publication_status.slug, 'en-revision',
        )

    # --------------------------- auditoria -----------------------------
    def test_el_envio_queda_registrado_con_lo_que_llego(self):
        self.enviar(descripcion='Pan casero de horno de leña')

        envio = Envio.objects.get()
        self.assertEqual(envio.colaborador, self.colaborador)
        self.assertEqual(envio.negocio, Business.objects.get())
        self.assertEqual(envio.estado, 'publicado')
        self.assertEqual(envio.datos['nombre'], 'Pan del Dia')
        self.assertEqual(
            envio.datos['descripcion'], 'Pan casero de horno de leña',
        )
        self.assertIsNotNone(envio.recibido_el)

        self.colaborador.refresh_from_db()
        self.assertIsNotNone(self.colaborador.ultimo_envio)

    def test_el_techo_por_minuto_corta_un_bombardeo(self):
        for i in range(LIMITE_ENVIOS_POR_MINUTO):
            response = self.enviar(
                nombre='Pan %02d' % i, telefono='8095551%04d' % i,
            )
            self.assertEqual(response.status_code, 201, response.content)

        response = self.enviar(nombre='Pan 99')

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            Business.objects.count(), LIMITE_ENVIOS_POR_MINUTO,
        )

    # ---------------------------- CSRF ---------------------------------
    def test_el_formulario_funciona_con_el_admin_abierto_en_el_mismo_dominio(self):
        """Regresion del CSRF, igual que el de las correcciones.

        DRF autentica por sesion por defecto: quien tenga la sesion del
        admin abierta le exigiria token CSRF — y esta herramienta y el
        admin estan en el MISMO dominio, asi que le pasaria a cualquiera
        que probara. Por eso el endpoint va con authentication_classes=[];
        este test es el que falla si alguien lo quita.
        """
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        User = get_user_model()
        client.force_login(
            User.objects.create_superuser('admin3', 'admin3@example.com', 'x')
        )

        response = self.enviar(cliente=client)

        self.assertEqual(response.status_code, 201, response.content)
