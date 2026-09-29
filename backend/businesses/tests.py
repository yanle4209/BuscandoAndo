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

from .models import Business, Correction

BUSINESSES_URL = '/api/businesses/'
FEATURED_BY_SEARCH_URL = '/api/businesses/featured-by-search/'
CORRECTIONS_URL = '/api/corrections/'


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
