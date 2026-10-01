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

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from .models import Business, Correction

BUSINESSES_URL = '/api/businesses/'
FEATURED_BY_SEARCH_URL = '/api/businesses/featured-by-search/'
CORRECTIONS_URL = '/api/corrections/'
CABECERAS_URL = '/api/cabeceras/'
PENDIENTES_URL = '/api/pendientes/'


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
    def admin(self):
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )
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

    def test_un_municipio_sin_fichas_da_404(self):
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        response = self.client.get(PENDIENTES_URL, {'municipio': 'Barahona'})

        self.assertEqual(response.status_code, 404)

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
