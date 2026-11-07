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
import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image

from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from business_images.models import BusinessImage
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from . import geografia, osm, portar, validacion
from .levantamiento import LIMITE_ENVIOS_POR_MINUTO, _ip
from .models import Business, Correction, Colaborador, Envio, Pospuesto, SlugAntiguo
from .serializers import BusinessListSerializer, compute_operational_status

BUSINESSES_URL = '/api/businesses/'
FEATURED_BY_SEARCH_URL = '/api/businesses/featured-by-search/'
CORRECTIONS_URL = '/api/corrections/'
CABECERAS_URL = '/api/cabeceras/'
PENDIENTES_URL = '/api/pendientes/'
POSPUESTO_URL = '/api/pospuesto/'
LEVANTAMIENTO_URL = '/api/levantamiento/'


def _foto(nombre='foto.jpg', color=(180, 120, 60)):
    """Un JPEG de verdad, chiquito: el canal abre la imagen con Pillow.

    El tamano no importa —se recorta a 1200x675 al guardar—; si importa
    que sea una imagen real, porque un archivo que no abre se rechaza
    en la puerta.
    """
    buf = io.BytesIO()
    Image.new('RGB', (80, 60), color).save(buf, format='JPEG')
    return SimpleUploadedFile(nombre, buf.getvalue(), 'image/jpeg')

# El admin maquilla las hojas con el storage con manifest, que solo
# resuelve despues de `collectstatic`: en los tests no hay manifest y la
# pagina de admin ni llegaria a pintarse.
STATIC_SIN_MANIFEST = {
    **settings.STORAGES,
    'staticfiles': {'BACKEND':
                    'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


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

    # ---------------------------- freno (E) ------------------------------
    def test_un_ip_que_empapa_el_formulario_recibe_429(self):
        """Sin techo server-side el formulario publico era una puerta
        abierta a inundar la bandeja del admin (auditoria E). El freno
        corta ANTES de la vista, asi que lo que llega de mas no se
        crea: el aviso repetido ni siquiera valida.

        El contador se pone a mano al techo (la suite entera manda ~18
        envios y no debe cruzar el limite sola) y se borra al terminar,
        para no depender del orden de los tests.
        """
        from config.middleware import ThrottleCorrecciones

        clave = ThrottleCorrecciones.PREFIJO + 'ip:127.0.0.1'
        self.addCleanup(cache.delete, clave)
        cache.set(clave, ThrottleCorrecciones.TECHO,
                  timeout=ThrottleCorrecciones.VENTANA)

        response = self.post()

        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        # Es un JsonResponse de Django (el freno va antes de DRF), no
        # una Response del framework: se lee el cuerpo a mano.
        cuerpo = json.loads(response.content.decode('utf-8'))
        self.assertIn('Demasiados', cuerpo['detail'])
        self.assertEqual(self.business.corrections.count(), 0)

    def test_el_freno_no_toca_a_los_demas(self):
        """Solo el POST publico cuenta: la lista (staff) no pasa por
        el freno aunque el techo este lleno."""
        from config.middleware import ThrottleCorrecciones

        clave = ThrottleCorrecciones.PREFIJO + 'ip:127.0.0.1'
        self.addCleanup(cache.delete, clave)
        cache.set(clave, ThrottleCorrecciones.TECHO,
                  timeout=ThrottleCorrecciones.VENTANA)

        response = self.client.get(CORRECTIONS_URL)

        self.assertIn(
            response.status_code, (401, 403),
            'El freno del POST publico se esta colando en la lista '
            'solo-staff',
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
        biz = Business.objects.create(
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
        # Con ubicacion de Moca (provincia de fase): los listados
        # recortan por provincia y una ficha sin location no sale.
        BusinessLocation.objects.create(
            business=biz, municipality='Moca', province='Espaillat',
            latitude=MOCA_LAT, longitude=MOCA_LNG,
        )
        return biz

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
        BusinessLocation.objects.create(
            business=biz, municipality='Moca', province='Espaillat',
            latitude=lat, longitude=lng,
        )
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
        biz = Business.objects.create(
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
        # En fase (Moca): los listados recortan por provincia.
        BusinessLocation.objects.create(
            business=biz, municipality='Moca', province='Espaillat',
            latitude=MOCA_LAT, longitude=MOCA_LNG,
        )
        return biz

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

    # --- Facilidad de uso: no hay que teclearlo todo ni teclearlo bien ---

    def test_con_una_palabra_del_titulo_se_encuentra(self):
        """'Crisostomo' contra 'Escuela Juan Crisóstomo Estrella'."""
        self.make_business('Escuela Juan Crisóstomo Estrella', featured=False)
        self.make_business('Farmacia Central', featured=False)

        self.assertEqual(
            self.abajo(text='crisostomo'),
            {'Escuela Juan Crisóstomo Estrella'},
        )

    def test_las_tildes_no_importan(self):
        """'nunez' encuentra 'Núñez' y escrito con tilde tambien."""
        self.make_business('Supermercado Núñez de Cáceres', featured=False)

        self.assertEqual(
            self.abajo(text='nunez'),
            {'Supermercado Núñez de Cáceres'},
        )
        self.assertEqual(
            self.abajo(text='núñez'),
            {'Supermercado Núñez de Cáceres'},
        )

    def test_el_orden_de_las_palabras_no_importa(self):
        """'estrella crisostomo' es el mismo negocio que al derecho."""
        self.make_business('Escuela Juan Crisóstomo Estrella', featured=False)

        self.assertEqual(
            self.abajo(text='estrella crisostomo'),
            {'Escuela Juan Crisóstomo Estrella'},
        )

    def test_una_errata_tambien_encuentra(self):
        """'crisostmo' (sin la o) sigue siendo el mismo sitio."""
        self.make_business('Escuela Juan Crisóstomo Estrella', featured=False)

        self.assertEqual(
            self.abajo(text='crisostmo'),
            {'Escuela Juan Crisóstomo Estrella'},
        )

    def test_una_errata_en_categoria_tambien_entra_arriba_y_abajo(self):
        """La tolerancia la aplican igual los destacados y el listado."""
        self.make_business('Cocina Dona Rosa', featured=True, tier='2')

        self.assertEqual(self.abajo(text='restarante'), {'Cocina Dona Rosa'})
        self.assertEqual(self.arriba(text='restarante'), {'Cocina Dona Rosa'})

    def test_un_texto_lejano_sigue_sin_inventar_resultados(self):
        """Tolerar erratas no es licencia para traer lo que se parezca."""
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

        self.assertEqual(self.abajo(text='crisostomo'), set())

    def test_una_busqueda_vacia_o_de_puntuacion_no_tira_el_listado(self):
        """Sin palabras que buscar no hay resultados, pero si respuesta 200."""
        self.make_business('Cocina Dona Rosa', featured=False)

        data = self.client.get(BUSINESSES_URL, {'text': '!!!'}).json()

        self.assertEqual(data['count'], 0)

    def test_lo_que_empieza_por_lo_buscado_sale_primero(self):
        """'panaderia la paz' no puede empezar por 'La Paz Panaderia'."""
        self.make_business('La Paz Panadería', featured=False)
        self.make_business('Panadería La Paz', featured=False)

        nombres = [b['name'] for b in
                   self.client.get(BUSINESSES_URL,
                                   {'text': 'panaderia la paz'}).json()['results']]

        self.assertEqual(nombres, ['Panadería La Paz', 'La Paz Panadería'])

    def test_la_errata_va_detras_de_lo_que_dice_el_nombre(self):
        """Lo que solo casaba por parecido no se cuela arriba."""
        self.make_business('Panadeira La Paz', featured=False)
        self.make_business('Panadería La Paz', featured=False)

        nombres = [b['name'] for b in
                   self.client.get(BUSINESSES_URL,
                                   {'text': 'panaderia la paz'}).json()['results']]

        self.assertEqual(nombres, ['Panadería La Paz', 'Panadeira La Paz'])

    def test_un_parecido_de_80_no_es_una_errata(self):
        """'crisostmo' no es 'cristo': 0.80 es ruido, no una errata."""
        self.make_business('Colegio Cristo Rey', featured=False)

        self.assertEqual(self.abajo(text='crisostmo'), set())


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class BusquedaEnAdminTests(TestCase):
    """El buscador del admin, con las mismas reglas que el de la web.

    La caja de busqueda del admin era un ``icontains`` campo a campo, y
    ahi la regla cuesta mas que en la web: "nunez" no encontraba
    "Supermercado Núñez de Cáceres", "crisostomo" no encontraba
    "Escuela Juan Crisóstomo Estrella" y una sola errata dejaba la
    busqueda vacia. Ahora la consulta pasa por la misma
    ``businesses.busqueda`` que la API publica (mezcla
    ``BusquedaAdmin``): una palabra basta, el orden no importa, las
    tildes sobran y una errata se perdona — y se busca tambien en la
    categoria, como en la web.
    """

    URL = '/admin/businesses/business/'
    COLABORADORES_URL = '/admin/businesses/colaborador/'

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')
        cls.restaurantes = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.admin = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')

    def ficha(self, nombre):
        return Business.objects.create(
            name=nombre, description='', category=self.restaurantes,
            publication_status=self.publicado,
            operational_status=self.abierto,
        )

    def buscar(self, q, url=None):
        self.client.force_login(self.admin)
        respuesta = self.client.get(url or self.URL, {'q': q})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def cuantos(self, q, url=None):
        return self.buscar(q, url).context['cl'].result_count

    def test_con_una_palabra_sin_tildes_se_encuentra(self):
        self.ficha('Escuela Juan Crisóstomo Estrella')
        self.ficha('Farmacia Central')

        respuesta = self.buscar('crisostomo')

        self.assertEqual(respuesta.context['cl'].result_count, 1)
        self.assertContains(respuesta, 'Escuela Juan Crisóstomo Estrella')
        self.assertNotContains(respuesta, 'Farmacia Central')

    def test_la_tilde_de_la_ficha_no_hace_falta_teclearla(self):
        self.ficha('Supermercado Núñez de Cáceres')

        self.assertContains(
            self.buscar('nunez'), 'Supermercado Núñez de Cáceres')

    def test_una_errata_tambien_se_perdona(self):
        self.ficha('Supermercado Núñez de Cáceres')

        self.assertContains(
            self.buscar('supermercdo'), 'Supermercado Núñez de Cáceres')

    def test_como_en_la_web_se_busca_tambien_en_la_categoria(self):
        """El nombre no lleva 'restaurante': solo la categoria."""
        self.ficha('Cocina Dona Rosa')

        self.assertContains(self.buscar('restaurante'), 'Cocina Dona Rosa')

    def test_un_texto_lejano_no_inventa_resultados(self):
        self.ficha('Farmacia Central')

        self.assertEqual(self.cuantos('crisostomo'), 0)

    def test_en_colaboradores_tambien_y_sin_duplicar_filas(self):
        """El queryset de ese listado viene con conteos anotados.

        El recorte por id no los puede romper ni repetir filas.
        """
        Colaborador.objects.create(nombre='José Pérez',
                                   municipio='Santo Domingo')
        Colaborador.objects.create(nombre='Pedro Rodriguez',
                                   municipio='Moca')

        self.assertEqual(self.cuantos('jose perez', self.COLABORADORES_URL), 1)
        self.assertEqual(self.cuantos('pedro', self.COLABORADORES_URL), 1)

    def test_en_el_admin_lo_que_mas_se_parece_sale_primero(self):
        """Django ordena la lista ANTES de llamar a buscar.

        La relevancia tiene que entrar por delante de ese orden, no
        quedarse detras: si no, "panaderia la paz" sale con "La Paz
        Panaderia" arriba por ser mas reciente.
        """
        self.ficha('La Paz Panadería')
        self.ficha('Panadería La Paz')

        html = self.buscar('panaderia la paz').content.decode()

        self.assertLess(html.index('Panadería La Paz'),
                        html.index('La Paz Panadería'))


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
            # Las dos provincias son de fase (FASE1): este test no mira
            # la fase, mira que `city` no recorte — y asi ambos salen.
            province='Espaillat' if municipio == 'Moca' else 'Santiago',
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
    """GET /api/cabeceras/ -> las cabeceras municipales de la fase (R3).

    Es el dato que hace que el sistema funcione y no solo donde hay
    fichas cargadas: ancla del circulo de 5 km cuando no hay GPS y
    fuente del selector manual. Con FASE1 activa la API publica solo
    las cabeceras de las provincias de fase; el padron COMPLETO (158)
    vive en ``geografia.cabeceras()`` y lo usan admin, importador y
    reporte de pendientes, que no pasan por aqui.
    """

    def cabeceras(self):
        response = self.client.get(CABECERAS_URL)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_es_publico_y_recorta_a_las_provincias_de_fase(self):
        data = self.cabeceras()
        padron = geografia.cabeceras()

        # FASE1: el publico ve solo las cabeceras de las provincias de
        # fase (22 de 158 hoy) y NINGUNA de fuera.
        fase = {geografia.normalizar(p) for p in settings.FASE1_PROVINCIAS}
        self.assertTrue(fase, 'los tests corren con la fase de settings')
        self.assertGreaterEqual(len(data), 1)
        for cab in data:
            with self.subTest(municipio=cab['municipio']):
                self.assertIn(geografia.normalizar(cab['provincia']), fase)

        # El padron de 158 del CSV no se toca: la fase recorta VISTAS.
        self.assertGreaterEqual(len(padron), 150)
        self.assertLess(len(data), len(padron))

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


class FaseGeograficaTests(TestCase):
    """FASE1: el listado y el selector recortan, la ficha no.

    Las provincias de fase (Espaillat, Santiago, La Vega y Hermanas
    Mirabal) es lo unico que se enseña HOY en web, app y levantamiento
    — los tres leen los mismos endpoints, asi que el recorte llega a
    todas de una sola vez. Las fichas de fuera siguen en la base (nada
    se borra), el enlace directo las sigue abriendo y vaciar
    ``FASE1_PROVINCIAS`` en settings vuelve al pais entero en un solo
    deploy.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.category = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')
        cls.en_fase = cls.ficha('La Receta', 'Moca', 'Espaillat',
                                19.3970, -70.5270)
        cls.fuera = cls.ficha('Dulce Hogar', 'Santo Domingo',
                              'Santo Domingo', 18.4861, -69.9312)

    @classmethod
    def ficha(cls, nombre, municipio, provincia, lat, lng):
        """Publicada y destacada: asi cubre listado Y destacados."""
        biz = Business.objects.create(
            name=nombre,
            description=f'Descripcion de {nombre}',
            short_description=nombre,
            category=cls.category,
            publication_status=cls.publicado,
            operational_status=cls.op_status,
            is_featured=True,
            featured_tier='2',
            featured_permanent=True,
        )
        BusinessLocation.objects.create(
            business=biz, municipality=municipio, province=provincia,
            latitude=lat, longitude=lng,
        )
        return biz

    def nombres(self, **params):
        data = self.client.get(BUSINESSES_URL, params).json()
        return [b['name'] for b in data['results']]

    def test_el_listado_solo_muestra_las_provincias_de_fase(self):
        """Sin coordenadas el listado mira al pais entero: entra la
        fase y solo la fase (antes devolvia las 1.839)."""
        self.assertEqual(self.nombres(), ['La Receta'])

    def test_el_recorte_no_borra_nada_de_la_base(self):
        """La ficha de fuera sigue ahi, publicada, esperando su dia."""
        self.assertTrue(
            Business.objects.filter(
                slug=self.fuera.slug,
                publication_status__slug='publicado',
            ).exists(),
        )

    def test_la_ficha_fuera_de_fase_abre_por_enlace_directo(self):
        """El enlace directo no se rompe: retrieve no pasa por el filtro."""
        response = self.client.get(f'{BUSINESSES_URL}{self.fuera.slug}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Dulce Hogar')

    def test_los_destacados_tambien_recortan(self):
        """Si no recortan igual, salen destacados sobre '0 resultados'."""
        data = self.client.get(BUSINESSES_URL, {'featured': 'true'}).json()

        self.assertEqual([b['name'] for b in data['results']],
                         ['La Receta'])

    def test_el_selector_de_municipio_solo_ofrece_la_fase(self):
        """El mismo endpoint leen web, app y levantamiento."""
        municipios = {
            c['municipio']
            for c in self.client.get(CABECERAS_URL).json()
        }

        self.assertIn('Moca', municipios)
        self.assertNotIn('Santo Domingo', municipios)

    @override_settings(FASE1_PROVINCIAS=())
    def test_sin_fase_configurada_entra_el_pais_entero(self):
        """La reversibilidad es un solo deploy: tupla vacia = antes."""
        self.assertEqual(sorted(self.nombres()),
                         ['Dulce Hogar', 'La Receta'])
        self.assertEqual(
            len(self.client.get(CABECERAS_URL).json()),
            len(geografia.cabeceras()),
        )


class ReportePendientesTests(TestCase):
    """GET /api/pendientes/ -> reporte de pendientes por municipio (§11.1).

    La ficha de trabajo con la que se edita y publica a mano lo que no
    llego a cumplir los obligatorios. Hay que proteger tres cosas:

    1. que **solo staff** la lea — dentro estan fichas sin publicar y el
       reparto de trabajo, y el DEFAULT_PERMISSION_CLASSES del proyecto es
       AllowAny;
    2. que agrupe por campo faltante **y marque lo obligatorio**: lo que
       sale de aqui es lo que un editor va a ir rellenando, y los
       obligatorios son los que deciden si una ficha se publica sola;
    3. que traiga **cabecera y radio**, que es lo que ancla el circulo de
       5 km con el que se mide si una ficha entrara en el municipio.

    Y lo nuevo de la regla del editor: DOS listas disjuntas —lo que falta
    obligatorio va a revision aunque este publicado, lo que solo trae
    opcionales va a la lista aparte de «publicadas con faltantes»—.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(name='Publicado', slug='publicado')
        cls.en_revision = PublicationStatus.objects.create(name='En Revision', slug='en-revision')
        cls.category = Category.objects.create(name='Restaurantes', slug='restaurantes')
        cls.op_status = OperationalStatus.objects.create(name='Abierto', slug='abierto')

        # Nada que pedir: publicada, completa y CON foto, no debe salir
        # ni en el contador ni en ninguna de las dos listas.
        cls.completa = cls.crear(
            'La Receta', telefono='809-555-1111', extras=True, horario=True,
        )
        # Cumple los obligatorios, pero no horario ni contacto extra: se
        # publica sola y entonces pasa a la lista APARTE de publicadas
        # con faltantes — fuera de la de revision, que es lo que pidio
        # el editor.
        cls.sin_extras = cls.crear('Panaderia Sol', telefono='809-555-2222')
        # Sin telefono no hay obligatorios -> queda en revision.
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
              procedencia='manual', horario=False, con_ubicacion=True,
              foto=True):
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
        # La foto es obligatoria: con ``foto=False`` se prueba que una
        # ficha sin ella vuelve a revision aunque este publicada.
        if foto:
            BusinessImage.objects.create(business=biz, image=_foto())
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
        # 'La Receta' esta publicada y completa: no es de nadie. Quedan
        # las dos sin publicar en revision, y 'Panaderia Sol' —publicada
        # y solo con extras sin completar— en la lista aparte.
        self.assertEqual(por_nombre['Moca']['con_revision'], 2)
        self.assertEqual(por_nombre['Moca']['con_publicadas'], 1)
        # Las dos de Moca sin publicar esperan publicarse.
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
        # 'La Receta' esta publicada y completa: no sale ni en la lista
        # de revision ni en la de publicadas con faltantes.
        self.assertEqual(datos['con_revision'], 2)
        nombres = [f['nombre'] for f in datos['fichas']]
        self.assertNotIn('La Receta', nombres)
        self.assertNotIn(
            'La Receta', [f['nombre'] for f in datos['publicadas']],
        )
        # 'Panaderia Sol' esta publicada y solo le faltan opcionales:
        # no es de revision; la lista aparte si la incluye.
        self.assertNotIn('Panaderia Sol', nombres)
        self.assertIn(
            'Panaderia Sol', [f['nombre'] for f in datos['publicadas']],
        )

    def test_agrupa_por_campo_faltante_y_marca_lo_obligatorio(self):
        """§11.1: agrupado por campo. Lo obligatorio va marcado para que
        se vea de un vistazo que es lo que bloquea la publicacion."""
        por_campo = {f['campo']: f for f in self.admin()['por_campo']}

        self.assertTrue(por_campo['telefono']['en_obligatorio'])
        self.assertTrue(por_campo['punto']['en_obligatorio'])
        self.assertFalse(por_campo['horario']['en_obligatorio'])
        self.assertGreaterEqual(por_campo['telefono']['cantidad'], 1)

    def test_lo_obligatorio_va_primero_en_la_cola(self):
        """Si no, los campos que no tiene casi nadie (WhatsApp, web)
        taparian el telefono, que es el que decide la publicacion."""
        from . import pendientes

        filas = self.admin()['por_campo']
        nombres = [f['campo'] for f in filas]

        ultimo_obligatorio = max(
            nombres.index(c) for c in pendientes.OBLIGATORIOS
            if c in nombres
        )
        primero_sin_obligatorio = min(
            i for i, fila in enumerate(filas)
            if not fila['en_obligatorio']
        )

        self.assertLess(ultimo_obligatorio, primero_sin_obligatorio)

    def test_una_publicada_con_faltantes_pasa_a_la_segunda_lista(self):
        """La regla del editor: la publicada con todos los obligatorios
        sale de la lista de revision —no estorba ahi— y aparece en la
        lista aparte de «publicadas con faltantes» para rellenarla mas
        adelante; el contador de la fila y la lista dicen lo mismo."""
        datos = self.admin()
        nombres = [f['nombre'] for f in datos['fichas']]

        # Publicada con extras sin completar: fuera de revision...
        self.assertNotIn('Panaderia Sol', nombres)
        # ...y en la lista aparte, con su falta a la vista.
        por_publicadas = {f['nombre']: f for f in datos['publicadas']}
        self.assertIn('Panaderia Sol', por_publicadas)
        self.assertIn('horario', por_publicadas['Panaderia Sol']['faltan'])
        # Publicada y completa: no sale en ninguna de las dos.
        self.assertNotIn('La Receta', nombres)
        self.assertNotIn('La Receta', por_publicadas)
        # Lo que queda en revision es exactamente lo que espera publicarse.
        self.assertTrue(
            all(f['estado'] == 'en-revision' for f in datos['fichas']),
        )
        self.assertEqual(datos['con_revision'], len(datos['fichas']))
        self.assertEqual(datos['con_publicadas'], len(datos['publicadas']))

    def test_una_publicada_sin_foto_vuelve_a_la_revision(self):
        """La foto es obligatoria: aunque ya este publicada, si se quedo
        sin imagen VUELVE a la lista de revision —con «imagen» marcado—
        hasta que alguien le ponga una."""
        self.crear(
            'Cafeteria El Parque', extras=True, horario=True, foto=False,
        )

        datos = self.admin()
        por_fichas = {f['nombre']: f for f in datos['fichas']}

        self.assertIn('Cafeteria El Parque', por_fichas)
        self.assertEqual(
            por_fichas['Cafeteria El Parque']['faltan'], ['imagen'],
        )
        self.assertNotIn(
            'Cafeteria El Parque',
            [f['nombre'] for f in datos['publicadas']],
        )
        self.assertEqual(datos['con_revision'], len(datos['fichas']))
        # Y en el desglose, «imagen» cuenta como obligatorio.
        por_campo = {f['campo']: f for f in datos['por_campo']}
        self.assertTrue(por_campo['imagen']['en_obligatorio'])

    def test_trae_la_procedencia(self):
        """§10: lo que viene del servicio entra marcado."""
        por_nombre = {f['nombre']: f for f in self.admin()['fichas']}

        self.assertEqual(por_nombre['Taller El Rayo']['procedencia'], 'importado')
        self.assertEqual(por_nombre['Kiosko La Esquina']['procedencia'], 'manual')

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
        # Solo las dos sin publicar; la publicada con faltantes va en la
        # lista aparte.
        self.assertEqual(datos[0]['con_revision'], 2)

    def test_el_reporte_le_dice_quien_firma(self):
        """La tarjeta «Tu firma» enseña el nombre del colaborador al que
        pertenece el token: viaja en el propio renglon, sin pedirlo por
        otra via ni adivinarlo en el navegador."""
        datos = self.con_token(self.colaborador('Moca')).json()

        self.assertEqual(datos[0]['colaborador'], 'Pedro')

    def test_la_lista_del_admin_no_lleva_nombre(self):
        """Quien no viene de un token no trae nombre de nadie: el
        listado entero es del admin, y el admin no firma nada."""
        self.loguear_admin()

        datos = self.client.get(PENDIENTES_URL).json()

        self.assertNotIn('colaborador', datos[0])

    def test_con_sesion_de_admin_abierta_el_token_sigue_mandando(self):
        """La sesion vive en el MISMO navegador que el token. Si alguien
        tiene el admin logueado y pega un token, tiene que ver SU
        municipio —no el primero de la lista entera, que era Azua."""
        self.loguear_admin()

        datos = self.con_token(self.colaborador('Moca')).json()

        self.assertEqual([f['municipio'] for f in datos], ['Moca'])
        self.assertEqual(datos[0]['colaborador'], 'Pedro')

    def test_un_token_invalido_da_401_aunque_haya_sesion_de_admin(self):
        """Quien trae un token que no vale no es quien no trae nada: se
        le avisa, aunque tenga la sesion del admin delante."""
        self.loguear_admin()

        response = self.client.get(
            PENDIENTES_URL,
            headers={'X-Colaborador-Token': 'esto-no-es-un-token'},
        )

        self.assertEqual(response.status_code, 401)

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

    # ---------------------- los obligatorios (R5) ---------------------
    def test_los_obligatorios_son_nombre_direccion_telefono_imagen_y_punto(self):
        """§10-f: el telefono, la direccion y la foto son obligatorios
        porque sin ellos la ficha no puede publicarse sola."""
        from . import pendientes

        self.assertTrue(pendientes.cumple_obligatorios(self.completa))
        self.assertFalse(pendientes.cumple_obligatorios(self.sin_telefono))
        self.assertFalse(pendientes.cumple_obligatorios(self.sin_coordenadas))
        # Sin direccion tampoco.
        sin_direccion = self.crear(
            'Sin Calle', calle='', extras=True, horario=True,
        )
        self.assertFalse(pendientes.cumple_obligatorios(sin_direccion))
        # Sin foto no se publica, aunque tenga todo lo demas.
        sin_foto = self.crear(
            'Sin Foto', extras=True, horario=True, foto=False,
        )
        self.assertFalse(pendientes.cumple_obligatorios(sin_foto))
        self.assertEqual(pendientes.faltantes_de(sin_foto), ['imagen'])

    def test_los_extras_no_son_obligatorios(self):
        """§10: horario y WhatsApp son pendientes, pero no impiden
        publicar. 'Panaderia Sol' no tiene ninguno de los dos."""
        from . import pendientes

        self.assertTrue(pendientes.cumple_obligatorios(self.sin_extras))
        self.assertIn('horario', pendientes.faltantes_de(self.sin_extras))


class FiltroYPospuestosTests(TestCase):
    """El reporte, categoria a categoria y con sus pospuestos.

    Dos cosas que pidio el editor para poder TRABAJAR con la lista en
    la mano:

    1. filtrar por categoria —«si me apetece solo trabajar las
       escuelas, las selecciono y trabajo con estas»— sin que el
       resumen, los chips ni el desglose mientan;
    2. posponer los negocios que no desea completar —o que no se
       pueden: eso es indiferente—: salen de sus listas a la de
       «pospuestos», guardadas en el servidor por dueno, para
       retomarlas cuando quiera.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado',
        )
        cls.en_revision = PublicationStatus.objects.create(
            name='En Revision', slug='en-revision',
        )
        cls.restaurantes = Category.objects.create(
            name='Restaurantes', slug='restaurantes',
        )
        cls.escuelas = Category.objects.create(name='Escuelas', slug='escuelas')
        cls.op_status = OperationalStatus.objects.create(
            name='Abierto', slug='abierto',
        )

        # Dos en cada categoria: al filtrar, cada lista se queda SOLO
        # con las suyas. Publicada sin extras -> «publicadas con
        # faltantes»; sin publicar -> «en revision».
        cls.resto_a = cls.crear('Panaderia Sol', cls.restaurantes)
        cls.resto_b = cls.crear(
            'Taller El Rayo', cls.restaurantes, publicada=False,
        )
        cls.cole_a = cls.crear('Escuela Central', cls.escuelas)
        cls.cole_b = cls.crear(
            'Colegio San Juan', cls.escuelas, publicada=False,
        )
        # Sin categoria: tiene su propio casillero en el filtro.
        cls.sin_cat = cls.crear('Puesto Ambulante', None, publicada=False)
        # Completa: no sale en ninguna lista ni en ningun filtro.
        cls.completa = cls.crear(
            'La Receta', cls.restaurantes, extras=True, horario=True,
        )

    @classmethod
    def crear(cls, nombre, categoria, *, publicada=True, extras=False,
              horario=False):
        biz = Business.objects.create(
            name=nombre,
            description='Descripcion de %s' % nombre,
            category=categoria,
            publication_status=(
                cls.publicado if publicada else cls.en_revision
            ),
            operational_status=cls.op_status,
            procedencia='manual',
        )
        BusinessLocation.objects.create(
            business=biz, street='Calle 1', municipality='Moca',
            province='Espaillat', latitude=MOCA_LAT, longitude=MOCA_LNG,
        )
        contacto = {'phone': '809-555-0000'}
        if extras:
            contacto = {
                'phone': '809-555-0000',
                'whatsapp': '+18095550000',
                'email': 'hola@example.com',
                'website': 'https://example.com',
            }
        BusinessContact.objects.create(business=biz, **contacto)
        if horario:
            BusinessHours.objects.create(
                business=biz, day='Lunes',
                open_time=datetime.time(8, 0),
                close_time=datetime.time(17, 0),
            )
        BusinessImage.objects.create(business=biz, image=_foto())
        return biz

    def loguear_admin(self):
        User = get_user_model()
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True, 'is_superuser': True,
            },
        )
        self.client.force_login(admin)

    def detalle(self, **params):
        """El detalle de Moca como lo ve el admin, con sus filtros."""
        self.loguear_admin()
        return self.client.get(
            PENDIENTES_URL, {'municipio': 'Moca', **params},
        ).json()

    def detalle_token(self, token, **params):
        """El mismo detalle con la vista DEL DUENO: su token, sus
        pospuestos (posponer es por dueno)."""
        return self.client.get(
            PENDIENTES_URL,
            {'municipio': 'Moca', **params},
            headers={'X-Colaborador-Token': token},
        ).json()

    def fila(self):
        """El renglon de Moca del listado, como lo ve el admin."""
        self.loguear_admin()
        filas = self.client.get(PENDIENTES_URL).json()
        return next(f for f in filas if f['municipio'] == 'Moca')

    def colaborador(self, municipio='Moca'):
        return Colaborador.objects.create(
            nombre='Pedro', municipio=municipio, activo=True,
        )

    def posponer(self, ficha, pospuesto=True, token=None):
        """El gesto del navegador: JSON, igual que lo manda axios."""
        encabezados = {'X-Colaborador-Token': token} if token else {}
        return self.client.post(
            POSPUESTO_URL,
            json.dumps({'ficha': ficha, 'pospuesto': pospuesto}),
            content_type='application/json',
            headers=encabezados,
        )

    # --------------------------- el filtro ----------------------------
    def test_el_filtro_de_categoria_solo_devuelve_las_suyas(self):
        datos = self.detalle(categoria='escuelas')

        self.assertEqual(
            [f['nombre'] for f in datos['fichas']], ['Colegio San Juan'],
        )
        self.assertEqual(
            [f['nombre'] for f in datos['publicadas']], ['Escuela Central'],
        )
        self.assertEqual(datos['total'], 2)

    def test_sin_filtro_siguen_estando_todas(self):
        """El filtro es una vista, no un guardado: sin parametro, el
        reporte es el de siempre."""
        datos = self.detalle()

        self.assertEqual(len(datos['fichas']), 3)
        self.assertEqual(len(datos['publicadas']), 2)
        self.assertEqual(datos['total'], 6)

    def test_el_desglose_de_categorias_es_del_mismo_reparto(self):
        """El numero del desplegable y el de la lista tienen que ser
        el mismo: salen del mismo reparto."""
        datos = self.detalle()

        por_slug = {c['slug']: c for c in datos['categorias']}
        self.assertEqual(
            {s: (c['con_revision'], c['con_publicadas'])
             for s, c in por_slug.items()},
            {
                'restaurantes': (1, 1),
                'escuelas': (1, 1),
                'sin-categoria': (1, 0),
            },
        )
        self.assertEqual(por_slug['escuelas']['nombre'], 'Escuelas')
        # La completa no cuenta: no es trabajo de nadie.
        self.assertEqual(sum(c['con_revision'] + c['con_publicadas']
                             for c in datos['categorias']), 5)

    def test_sin_categoria_tiene_su_casillero(self):
        datos = self.detalle(categoria='sin-categoria')

        self.assertEqual(
            [f['nombre'] for f in datos['fichas']], ['Puesto Ambulante'],
        )
        self.assertEqual(datos['publicadas'], [])
        self.assertEqual(datos['total'], 1)

    def test_el_resumen_con_filtro_cuenta_lo_de_la_categoria(self):
        """El «esperando publicarse» del resumen es el de la categoria
        elegida, no el del municipio entero."""
        sin_filtro = self.detalle()
        con_filtro = self.detalle(categoria='escuelas')

        self.assertEqual(sin_filtro['en_revision'], 3)
        self.assertEqual(con_filtro['en_revision'], 1)

    def test_los_chips_con_filtro_solo_cuentan_las_suyas(self):
        """«Por campo faltante» mide la categoria: sin filtro hay 5
        fichas sin horario, con el de escuelas, solo 2."""
        sin_filtro = self.detalle()
        con_filtro = self.detalle(categoria='escuelas')

        def horario(datos):
            return next(
                c['cantidad'] for c in datos['por_campo']
                if c['campo'] == 'horario'
            )

        self.assertEqual(horario(sin_filtro), 5)
        self.assertEqual(horario(con_filtro), 2)

    # -------------------------- los pospuestos ------------------------
    def test_se_puede_posponer_una_ficha_y_sale_de_sus_listas(self):
        self.loguear_admin()
        respuesta = self.posponer(self.resto_b.id)

        self.assertEqual(respuesta.status_code, 200)
        datos = self.detalle()
        self.assertNotIn(
            'Taller El Rayo', [f['nombre'] for f in datos['fichas']],
        )
        self.assertEqual(
            [f['nombre'] for f in datos['pospuestos']], ['Taller El Rayo'],
        )
        # Y la fila del listado dice lo mismo que la lista.
        self.assertEqual(datos['con_revision'], 2)
        renglon = self.fila()
        self.assertEqual(renglon['con_revision'], 2)
        self.assertEqual(renglon['con_pospuestos'], 1)
        self.assertEqual(renglon['total'], 6)

    def test_retomar_la_devuelve_a_su_lista(self):
        self.loguear_admin()
        self.posponer(self.resto_b.id)
        self.posponer(self.resto_b.id, pospuesto=False)

        datos = self.detalle()
        self.assertIn(
            'Taller El Rayo', [f['nombre'] for f in datos['fichas']],
        )
        self.assertEqual(datos['pospuestos'], [])
        self.assertEqual(self.fila()['con_pospuestos'], 0)

    def test_posponer_es_por_dueno(self):
        """Lo que uno pospone no le estorba al otro: cada uno tiene
        las suyas."""
        token = self.colaborador().token
        self.posponer(self.resto_b.id, token=token)

        # Pedro, con SU lista, la ve pospuesta y fuera de revision.
        suyo = self.client.get(
            PENDIENTES_URL,
            {'municipio': 'Moca'},
            headers={'X-Colaborador-Token': token},
        ).json()
        self.assertNotIn(
            'Taller El Rayo', [f['nombre'] for f in suyo['fichas']],
        )
        self.assertEqual(
            [f['nombre'] for f in suyo['pospuestos']], ['Taller El Rayo'],
        )

        # El admin, con SU lista, sigue viendola en revision.
        self.assertIn(
            'Taller El Rayo',
            [f['nombre'] for f in self.detalle()['fichas']],
        )

    def test_un_colaborador_no_pospone_fichas_de_otro_municipio(self):
        token = self.colaborador('Santiago').token

        respuesta = self.posponer(self.resto_b.id, token=token)

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn('otro municipio', respuesta.json()['detail'])
        self.assertIn(
            'Taller El Rayo',
            [f['nombre'] for f in self.detalle()['fichas']],
        )

    def test_posponer_sin_firma_da_403(self):
        respuesta = self.posponer(self.resto_b.id)

        self.assertEqual(respuesta.status_code, 403)

    def test_un_token_que_no_es_de_nadie_da_401_al_posponer(self):
        respuesta = self.posponer(self.resto_b.id, token='no-existe')

        self.assertEqual(respuesta.status_code, 401)

    def test_posponer_sin_ficha_pide_la_ficha(self):
        self.loguear_admin()
        respuesta = self.posponer('')

        self.assertEqual(respuesta.status_code, 400)

    def test_una_ficha_completada_no_sigue_pospuesta(self):
        """La que se completo despues de posponerla —o que ya estaba
        completa— no vuelve a estorbar en la lista de pospuestos."""
        self.loguear_admin()
        self.posponer(self.completa.id)

        datos = self.detalle()
        self.assertEqual(datos['pospuestos'], [])
        self.assertEqual(self.fila()['con_pospuestos'], 0)

    def test_pospuestos_y_filtro_se_aplican_a_la_misma_vez(self):
        """Las pospuestas de la categoria elegida salen en SU lista;
        en las demas, no."""
        token = self.colaborador().token
        self.posponer(self.cole_b.id, token=token)

        escuelas = self.detalle_token(token, categoria='escuelas')
        self.assertEqual(
            [f['nombre'] for f in escuelas['pospuestos']],
            ['Colegio San Juan'],
        )
        self.assertEqual(escuelas['con_revision'], 0)

        restaurantes = self.detalle_token(token, categoria='restaurantes')
        self.assertEqual(restaurantes['pospuestos'], [])

    def test_una_categoria_entera_pospuesta_sigue_en_el_desplegable(self):
        """Si se pospone todo, la categoria no puede desaparecer del
        desplegable: su valor actual se quedaría sin opciones y el
        select saldria en blanco."""
        token = self.colaborador().token
        self.posponer(self.cole_a.id, token=token)
        self.posponer(self.cole_b.id, token=token)

        datos = self.detalle_token(token, categoria='escuelas')

        por_slug = {c['slug']: c for c in datos['categorias']}
        self.assertIn('escuelas', por_slug)
        self.assertEqual(por_slug['escuelas']['con_revision'], 0)
        self.assertEqual(por_slug['escuelas']['con_publicadas'], 0)
        self.assertEqual(datos['fichas'], [])
        self.assertEqual(datos['publicadas'], [])
        self.assertEqual(len(datos['pospuestos']), 2)

    # ---------------------------- CSRF ---------------------------------
    def test_posponer_con_sesion_de_admin_y_token_csrf(self):
        """Regresion: el boton Posponer con el admin abierto (CSRF).

        DRF autentica por sesion por defecto: quien tiene la sesion del
        admin en el MISMO dominio pasa por SessionAuthentication y
        este exige el token CSRF — sin cabecera, el POST devolvia
        «CSRF token missing» y el boton no hacia nada (el aviso del
        navegador lo mostraba). El index reparte la cookie (get_token)
        y el axios de la SPA la manda en X-CSRFToken; este test es el
        que falla si eso se quita.
        """
        from django.test import Client

        # enforce_csrf_checks=True porque el cliente de pruebas se salta
        # la validacion de CSRF POR DEFECTO: sin el, el test pasaria
        # tambien con el codigo roto y no serviria de nada.
        cliente = Client(enforce_csrf_checks=True)
        User = get_user_model()
        cliente.force_login(User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True, 'is_superuser': True,
            },
        )[0])

        # La cookie csrftoken guarda el secreto (32, CSRF_SECRET_LENGTH)
        # y el navegador lo manda tal cual en la cabecera.
        secreto = 'a' * 32
        cliente.cookies['csrftoken'] = secreto
        cuerpo = json.dumps({'ficha': self.resto_b.id, 'pospuesto': True})

        sin = cliente.post(
            POSPUESTO_URL, cuerpo, content_type='application/json',
        )
        self.assertEqual(sin.status_code, 403, sin.content)
        self.assertIn('CSRF', sin.json()['detail'])

        con = cliente.post(
            POSPUESTO_URL, cuerpo, content_type='application/json',
            headers={'X-CSRFToken': secreto},
        )
        self.assertEqual(con.status_code, 200, con.content)
        self.assertTrue(
            Pospuesto.objects.filter(negocio=self.resto_b).exists(),
        )


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
    por no cumplir los obligatorios, los que mas necesitamos (los que no
    tienen telefono) no llegarian nunca al reporte de §11.1.
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

    def test_faltar_lo_obligatorio_no_rechaza(self):
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
        """R1: por defecto el circulo sigue siendo de 5 km, que es lo que
        mide el importador. El canal de envio lo apaga, con radio_km
        None: el municipio ya lo garantiza el token."""
        motivos = self.validar(lat=19.4400, lng=-70.5274)  # ~4.85 km

        self.assertEqual(motivos, [])

        motivos = self.validar(lat=19.4460, lng=-70.5274)  # ~5.51 km

        self.assertEqual(len(motivos), 1)

        # Sin circulo no hay distancia que enrostrar: la MISMA coordenada
        # pasa limpia.
        motivos = self.validar(
            lat=19.4460, lng=-70.5274, radio_km=None,
        )

        self.assertEqual(motivos, [])

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

    def test_de_varios_numeros_se_parten_todos(self):
        """El negocio con mas de uno: la cadena se parte con el mismo
        separador de OSM. (Ese recorte al primero es del importador, en
        ``limpiar_telefono``; el canal si guarda todos.)"""
        self.assertEqual(
            validacion.partir_telefonos('809-555-1111; 809-555-2222'),
            ['809-555-1111', '809-555-2222'],
        )
        self.assertEqual(
            validacion.partir_telefonos('809-1,809-2/809-3|809-4'),
            ['809-1', '809-2', '809-3', '809-4'],
        )
        self.assertEqual(validacion.partir_telefonos(''), [])
        self.assertEqual(validacion.partir_telefonos('  ;  '), [])

    def test_toda_la_cadena_de_telefonos_tiene_que_ser_llamable(self):
        self.assertTrue(
            validacion.telefonos_valido('809-555-1111; 809-555-2222'),
        )
        # Un solo malo entre los buenos echa atras el envio entero.
        self.assertFalse(validacion.telefonos_valido('809-555-1111; 123'))
        self.assertFalse(validacion.telefonos_valido(''))

    def test_varios_telefonos_validos_pasan_la_puerta(self):
        motivos = self.validar(telefono='809-555-1111; 809-555-2222')

        self.assertEqual(motivos, [])

    def test_un_telefono_malo_en_la_cadena_se_rechaza(self):
        motivos = self.validar(telefono='809-555-1111; no-telefono')

        self.assertEqual(len(motivos), 1)
        self.assertIn('formato valido', motivos[0])

    def test_se_aceptan_hasta_cinco_telefonos(self):
        """El mismo techo razonable que las fotos: cinco, y el resto
        que se quede el numero del directorio."""
        cadena = '; '.join('809-555-%04d' % i for i in range(1, 7))

        motivos = self.validar(telefono=cadena)

        self.assertEqual(len(motivos), 1)
        self.assertIn('hasta 5 telefonos', motivos[0])

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


class _Respuesta:
    """Lo minimo de una respuesta HTTP para usarla en ``with`` + ``read``."""

    def __init__(self, cuerpo):
        self._cuerpo = cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._cuerpo.encode('utf-8')


class ConsultarOverpassTests(TestCase):
    """``osm.consultar`` tiene que separar tres salidas distintas.

    Contesto y hay datos -> la lista. Nadie contesto -> ``None``. Y la
    tercera, que es la que se cuela: **contesto pero se le acabo el
    tiempo en el servidor** — Overpass devuelve 200 con ``elements: []``
    y un ``remark``. Leer eso como "aqui no hay nada" deja el municipio
    sin fichas y sin que nadie se entera, que es exactamente lo que la
    docstring de ``consultar`` dice que hay que evitar.
    """

    CABECERA = {'lat': 19.76008, 'lng': -71.67318}

    @staticmethod
    def contestar(cuerpo):
        return lambda *args, **kwargs: _Respuesta(cuerpo)

    @patch('businesses.osm.PAUSA_SEGUNDOS', 0)
    @patch('businesses.osm.urllib.request.urlopen')
    def test_un_remark_no_lo_tomo_como_un_municipio_vacio(self, urlopen):
        """El primer servidor se le acabo el tiempo; el segundo contesta."""
        urlopen.side_effect = [
            _Respuesta(json.dumps({'elements': [], 'remark': 'timeout'})),
            _Respuesta(json.dumps({'elements': [{'id': 1}]})),
        ]

        elementos = osm.consultar(self.CABECERA, 5)

        self.assertEqual([e['id'] for e in elementos], [1])
        self.assertEqual(urlopen.call_count, 2)

    @patch('businesses.osm.PAUSA_SEGUNDOS', 0)
    @patch('businesses.osm.urllib.request.urlopen')
    def test_si_nadie_contesto_eso_no_es_un_vacio(self, urlopen):
        """Si todos responden con remark, es ``None``: sin datos, no vacio."""
        urlopen.side_effect = self.contestar(
            json.dumps({'elements': [], 'remark': 'timeout'}),
        )

        self.assertIsNone(osm.consultar(self.CABECERA, 5))


class ImportarMunicipioTests(TestCase):
    """``manage.py importar_municipio`` -> R5 en la practica.

    Tres pasos dependen del anterior y hay que protegerlos en ese orden:
    validar ANTES de crear, cruzar ANTES de publicar, y publicar SOLO con
    los obligatorios —que incluyen la foto, que OSM no trae: lo nuevo se
    queda en revision—. El cuarto, que no se ve a primera vista: lo
    creado a mano nunca se publica solo (VISION.md).
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

    def hacer_manual(self, nombre, procedencia='manual'):
        """Una ficha sin publicar, en el circulo de Moca."""
        biz = Business.objects.create(
            name=nombre,
            description='Descripcion',
            publication_status=self.en_revision,
            operational_status=self.abierto,
            procedencia=procedencia,
        )
        BusinessLocation.objects.create(
            business=biz, street='Calle 1 #10', municipality='Moca',
            province='Espaillat', latitude=19.3970, longitude=-70.5270,
        )
        return biz

    # ---------------------- R5: que se publica --------------------------
    @patch('businesses.osm.consultar')
    def test_sin_foto_no_se_publica(self, consultar):
        """La foto es obligatoria: OSM no la trae, y sin ella la ficha
        se queda en revision aunque cumpla todo lo demas — es la
        regla del editor, y nada se descarta por eso."""
        consultar.return_value = [
            nodo('Pan del Dia', phone='809-555-1111'),
        ]

        self.importar()

        pan = Business.objects.get(name='Pan del Dia')

        self.assertEqual(pan.publication_status.slug, 'en-revision')
        self.assertEqual(pan.procedencia, 'importado')

    @patch('businesses.osm.consultar')
    def test_una_importada_con_foto_se_publica_al_completarse(self, consultar):
        """El importador sigue publicando cuando se cumplen los
        obligatorios: la ficha ya existia CON foto y OSM trae el
        telefono que le faltaba."""
        existente = self.hacer_manual(
            'Pan del Dia', procedencia='importado',
        )
        BusinessImage.objects.create(business=existente, image=_foto())
        consultar.return_value = [
            nodo('Pan del Dia', phone='809-555-1111'),
        ]

        self.importar()

        existente.refresh_from_db()

        self.assertEqual(existente.publication_status.slug, 'publicado')
        self.assertEqual(existente.contact.phone, '809-555-1111')

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

    def enviar(self, token=None, cliente=None, fotos=1, **extra):
        """Un POST al canal, en multipart como el formulario de verdad.

        ``token=None`` manda el bueno; '' ninguno. Trae ``fotos`` por
        defecto porque el alta las exige: ``fotos=0`` prueba esa misma
        obligacion y ``fotos=6`` el techo. Los ``None`` no viajan —el
        multipart no sabe codificarlos— y ausente es igual que null
        para el servidor.
        """
        if token is None:
            token = self.colaborador.token
        encabezados = {'X-Colaborador-Token': token} if token else {}
        cuerpo = {
            clave: valor
            for clave, valor in self.cuerpo(**extra).items()
            if valor is not None
        }
        cuerpo['imagenes'] = [_foto('foto%d.jpg' % i) for i in range(fotos)]
        return (cliente or self.client).post(
            LEVANTAMIENTO_URL,
            cuerpo,
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

    def test_las_referencias_llegan_y_se_guardan(self):
        """Un campo mas en «Dode esta»: no decide nada — no es de lo
        obligatorio ni del reporte — pero sirve para llegar a pie, y
        tiene que sobrevivir el viaje entero hasta la ficha."""
        response = self.enviar(referencias='Frente a la parada del bus')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            BusinessLocation.objects.get().referencias,
            'Frente a la parada del bus',
        )

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
        cuerpo = {
            clave: valor
            for clave, valor in self.cuerpo().items()
            if valor is not None
        }
        cuerpo['imagenes'] = [_foto()]

        response = self.client.post(
            LEVANTAMIENTO_URL,
            cuerpo,
            headers={'Authorization': 'Bearer ' + self.colaborador.token},
        )

        self.assertEqual(response.status_code, 201, response.content)

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

    def test_un_punto_lejano_de_la_cabecera_si_entra(self):
        """Ya nadie mide contra la cabecera: el municipio lo garantiza el
        token (§11-i). Esas coordenadas estan a unos 9.8 km del centro —
        justo el aviso que salia en la pantalla— y dejan de ser motivo de
        rechazo: el circulo de 5 km es el del BUSCADOR (R1), no el de
        quien levanta la ficha."""
        response = self.enviar(lat=19.6000)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Business.objects.count(), 1)

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

    # --------------------------- las fotos -----------------------------
    def test_una_ficha_nueva_sin_foto_se_rechaza(self):
        """La foto es obligatoria hasta que la ficha tenga una.

        Sin foto no hay ficha nueva que valga: se rechaza en la puerta
        y no queda pendiente de nada (§11.5), igual que lo mal formado.
        """
        response = self.enviar(fotos=0)

        self.assertEqual(response.status_code, 400)
        self.assertIn('foto', ' '.join(response.data['motivos']).lower())
        self.assertEqual(Business.objects.count(), 0)
        self.assertEqual(Envio.objects.get().estado, 'rechazado')

    def test_las_fotos_entran_con_la_ficha(self):
        response = self.enviar()

        self.assertEqual(response.status_code, 201, response.content)
        negocio = Business.objects.get()
        self.assertEqual(negocio.images.count(), 1)
        # La regla del admin: WebP con el nombre del original.
        self.assertTrue(negocio.images.get().image.name.endswith('.webp'))
        self.assertEqual(response.data['imagenes'], 1)
        # La auditoria guarda los nombres de lo que llego.
        self.assertEqual(Envio.objects.get().datos['imagenes'], ['foto0.jpg'])

    def test_seis_fotos_no_entran(self):
        response = self.enviar(fotos=6)

        self.assertEqual(response.status_code, 400)
        self.assertIn('5', ' '.join(response.data['motivos']))
        self.assertEqual(Business.objects.count(), 0)

    def test_un_archivo_que_no_es_imagen_se_rechaza(self):
        cuerpo = {
            clave: valor
            for clave, valor in self.cuerpo().items()
            if valor is not None
        }
        cuerpo['imagenes'] = [
            SimpleUploadedFile('nota.txt', b'no soy una imagen', 'text/plain'),
        ]

        response = self.client.post(
            LEVANTAMIENTO_URL, cuerpo,
            headers={'X-Colaborador-Token': self.colaborador.token},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('imagen', ' '.join(response.data['motivos']).lower())
        self.assertEqual(Business.objects.count(), 0)

    def test_el_multipart_trae_el_horario_como_texto_y_el_cerrado(self):
        """Lo que el formulario manda como texto tiene que leerse igual.

        En multipart TODO llega como cadena: sin esto el horario se
        perdia —no es lista— y ``bool('false')`` daria True —todo
        saldria cerrado—.
        """
        OperationalStatus.objects.create(name='Cerrado', slug='cerrado')

        response = self.enviar(
            cerrado='true',
            horario='[{"dia": "Lunes", "desde": "08:00", "hasta": "17:00"}]',
        )

        self.assertEqual(response.status_code, 201, response.content)
        negocio = Business.objects.get()
        self.assertEqual(negocio.operational_status.slug, 'cerrado')
        self.assertEqual(negocio.hours.count(), 1)
        envio = Envio.objects.get()
        self.assertEqual(len(envio.datos['horario']), 1)
        self.assertTrue(envio.datos['cerrado'])

    def test_un_cerrado_false_del_multipart_no_cierra_nada(self):
        OperationalStatus.objects.create(name='Cerrado', slug='cerrado')

        response = self.enviar(cerrado='false')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            Business.objects.get().operational_status.slug, 'abierto',
        )
        self.assertFalse(Envio.objects.get().datos['cerrado'])

    # ----------------------- 3. los obligatorios -----------------------
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

    def test_pueden_llegar_varios_telefonos(self):
        """El negocio con mas de uno: la cadena entra entera y el
        contacto se queda con los dos, tal cual los escribio quien
        levanto la ficha (la ficha publica los pinta cada uno con su
        enlace tel:)."""
        response = self.enviar(telefono='809-555-1111; 809-555-2222')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            BusinessContact.objects.get(
                business=Business.objects.get(),
            ).phone,
            '809-555-1111; 809-555-2222',
        )
        self.assertEqual(response.data['estado'], 'publicado')

    def test_sin_punto_queda_pendiente(self):
        """Falta un obligatorio, no esta roto: tambien entra."""
        response = self.enviar(lat=None, lng=None)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['estado'], 'pendiente')
        self.assertIn('punto', response.data['faltan'])

    def test_una_categoria_desconocida_no_se_crea_desde_aqui(self):
        """Sin la bandera de crear, una errata no abre una categoria
        nueva al sistema: aqui teclea una persona y solo se busca la
        que ya hay. Con la bandera si se crea (test de al lado); el
        importador la crea siempre, porque el nombre viene de OSM."""
        response = self.enviar(categoria='Pan (con errata)')

        self.assertFalse(Category.objects.filter(name='Pan (con errata)').exists())
        # Y no por eso se le retiene: la categoria no es de lo obligatorio.
        self.assertEqual(response.data['estado'], 'publicado')
        self.assertIn('categoria', response.data['faltan'])

    def test_con_la_bandera_se_crea_la_categoria_en_el_momento(self):
        """Validacion inmediata: el formulario no encontro la suya, la
        pide crear y el servidor la valida y la da de alta en el envio.
        La respuesta lo dice, para que el formulario pueda confirmarlo."""
        response = self.enviar(
            categoria='Panaderia Nueva', categoria_nueva=True,
        )

        self.assertEqual(response.status_code, 201, response.content)
        creada = Category.objects.get(name='Panaderia Nueva')
        self.assertEqual(Business.objects.get().category, creada)
        self.assertNotIn('categoria', response.data['faltan'])
        self.assertEqual(response.data['categoria_creada'], 'Panaderia Nueva')
        self.assertIsNone(response.data['categoria_reusada'])

    def test_la_categoria_nueva_no_se_duplica_si_ya_esta(self):
        """La dedupe es sin distinguir mayusculas: 'PANADERIAS' es la
        'Panaderias' que ya esta, no una segunda. Y la respuesta lo
        cuenta como reusada, no como creada: no se creo nada."""
        response = self.enviar(categoria='PANADERIAS', categoria_nueva=True)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Business.objects.get().category, self.category)
        self.assertEqual(response.data['categoria_reusada'], 'Panaderias')
        self.assertIsNone(response.data['categoria_creada'])

    def test_si_el_slug_ya_es_de_otra_se_reutiliza(self):
        """'Panaderias!' da el mismo slug que 'Panaderias': crearla
        reventaria el unique, y con una basta."""
        response = self.enviar(categoria='Panaderias!', categoria_nueva=True)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Business.objects.get().category, self.category)
        self.assertEqual(response.data['categoria_reusada'], 'Panaderias')

    def test_crear_categoria_sin_nombre_se_rechaza(self):
        response = self.enviar(categoria='', categoria_nueva=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'categoria', ' '.join(response.data['motivos']).lower(),
        )
        # Solo la del setup: nada se creo.
        self.assertEqual(Category.objects.count(), 1)

    def test_la_categoria_no_se_crea_si_el_envio_se_rechaza(self):
        """La categoria solo nace con un envio aceptado: si el resto
        falla —ahi, sin foto— no queda una hoja suelta en la tabla de
        lo que nunca llego a ser ficha, y el rechazo no promete nada."""
        response = self.enviar(
            categoria='Panaderia Nueva', categoria_nueva=True, fotos=0,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Category.objects.filter(name='Panaderia Nueva').exists(),
        )
        self.assertEqual(Category.objects.count(), 1)

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

    def test_un_envio_que_publica_no_deja_pendiente(self):
        """La otra mitad del circuito: si el envio trae los obligatorios,
        la ficha se publica y **no entra** en la lista de revision,
        aunque le falten extras opcionales — asi lo pidio el editor."""
        self.enviar()
        User = get_user_model()
        self.client.force_login(
            User.objects.create_superuser('admin', 'admin@example.com', 'x')
        )

        response = self.client.get(PENDIENTES_URL, {'municipio': 'Moca'})

        nombres = [f['nombre'] for f in response.data['fichas']]
        self.assertNotIn('Pan del Dia', nombres)
        self.assertEqual(response.data['con_revision'], 0)
        # Con extras sin completar si aparece: en la lista aparte.
        self.assertIn(
            'Pan del Dia',
            [f['nombre'] for f in response.data['publicadas']],
        )

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

    def test_completarle_lo_obligatorio_a_una_importada_la_publica(self):
        """§10-d + §10-f, juntas.

        La ficha existente es una importada sin telefono ni foto; el
        envio trae las dos. Se le completan **y** se publica, porque ya
        cumple todo lo obligatorio. Es la prueba de que hay que releer la
        instancia: si no, `cumple_obligatorios` veria la cache de "no
        tiene contacto" de antes de crearlo y se quedaria en revision.
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


class CompletarFichaTests(TestCase):
    """Fase D: completar la ficha que YA existe (§11.1 + §11-i).

    El colaborador no manda datos al aire: elige una ficha de SU reporte,
    el formulario sale rellenado y lo que el rellena se escribe EN ESA
    ficha. Las dos garantias que hay que proteger con mas cuidado son que
    no se cree una segunda ficha por completar esta, y que no se escriba
    en el municipio de otro.
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
        cls.category = Category.objects.create(
            name='Panaderias', slug='panaderias',
        )
        cls.colaborador = Colaborador.objects.create(
            nombre='Pedro', municipio='Moca',
        )

    # ------------------------------ utilidades -------------------------
    def hacer_ficha(self, *, telefono='', descripcion='Pan artesanal',
                    categoria=True, con_estado=True, municipio='Moca'):
        """Una ficha en revision, con lo justo para que le falte algo."""
        negocio = Business.objects.create(
            name='Pan del Dia',
            description=descripcion,
            category=self.category if categoria else None,
            publication_status=self.en_revision,
            operational_status=self.abierto if con_estado else None,
            procedencia='importado',
        )
        BusinessLocation.objects.create(
            business=negocio, street='Calle 1 #10', municipality=municipio,
            province='Espaillat', latitude=19.3970, longitude=-70.5270,
        )
        if telefono:
            BusinessContact.objects.create(business=negocio, phone=telefono)
        return negocio

    def completar(self, ficha=None, token=None, id_ficha=None, fotos=1,
                  **extra):
        """Un POST en modo completar, en multipart como el formulario.

        ``id_ficha`` sirve para probar ids que no existen, que no se
        pueden sacar de una ficha de verdad. Las fichas de aqui no
        tienen foto, y completar una ficha sin foto exige mandar al
        menos una: por eso el default trae ``fotos=1`` y ``fotos=0``
        prueba ese mismo rechazo.
        """
        if token is None:
            token = self.colaborador.token
        cuerpo = {
            'ficha': ficha.pk if ficha is not None else id_ficha,
            'nombre': 'Pan del Dia',
            'telefono': '809-555-1111',
            'lat': 19.3970,
            'lng': -70.5270,
            'municipio': 'Moca',
        }
        cuerpo.update(extra)
        cuerpo = {
            clave: valor
            for clave, valor in cuerpo.items()
            if valor is not None
        }
        cuerpo['imagenes'] = [_foto('foto%d.jpg' % i) for i in range(fotos)]
        return self.client.post(
            LEVANTAMIENTO_URL, cuerpo,
            headers={'X-Colaborador-Token': token} if token else {},
        )

    def pedir_ficha(self, ficha, token=None):
        if token is None:
            token = self.colaborador.token
        return self.client.get(
            f'{PENDIENTES_URL}?ficha={ficha.pk}',
            headers={'X-Colaborador-Token': token} if token else {},
        )

    # ------------------------ completar una ----------------------------
    def test_completa_la_ficha_elegida_sin_crear_una_segunda(self):
        ficha = self.hacer_ficha()

        response = self.completar(ficha)

        self.assertEqual(response.status_code, 200, response.content)
        # La garantia entera en un renglon: seguir siendo UNA.
        self.assertEqual(Business.objects.count(), 1)
        self.assertEqual(
            BusinessContact.objects.get(business=ficha).phone,
            '809-555-1111',
        )
        self.assertEqual(response.json()['completado'], ['contacto'])

    def test_no_sobrescribe_lo_que_la_ficha_ya_tiene(self):
        ficha = self.hacer_ficha(telefono='809-111-2222')

        response = self.completar(ficha)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            BusinessContact.objects.get(business=ficha).phone,
            '809-111-2222',
        )
        self.assertNotIn('phone', response.json()['completado'])

    def test_rellena_lo_que_el_reporte_marca_como_faltante(self):
        ficha = self.hacer_ficha(descripcion='', categoria=False)

        response = self.completar(
            ficha, telefono='', descripcion='Pan artesanal',
            categoria='Panaderias',
        )

        self.assertEqual(response.status_code, 200, response.content)
        ficha.refresh_from_db()
        self.assertEqual(ficha.description, 'Pan artesanal')
        self.assertEqual(ficha.category, self.category)
        completado = response.json()['completado']
        self.assertIn('descripcion', completado)
        self.assertIn('categoria', completado)

    def test_se_publica_en_cuanto_cumple_lo_obligatorio(self):
        ficha = self.hacer_ficha()
        self.assertEqual(ficha.publication_status, self.en_revision)

        response = self.completar(ficha)

        self.assertEqual(response.json()['estado'], 'publicado')
        ficha.refresh_from_db()
        self.assertEqual(ficha.publication_status, self.publicado)
        self.assertNotIn('telefono', response.json()['faltan'])

    def test_una_ficha_ya_publicada_sigue_publicada_si_solo_se_le_completa_algo(self):
        ficha = self.hacer_ficha(telefono='809-111-2222')
        ficha.publication_status = self.publicado
        ficha.save()

        response = self.completar(ficha, descripcion='Pan del dia y bolleria')

        # Estado de la ficha DESPUES, no "lo que se acabo de promover".
        self.assertEqual(response.json()['estado'], 'publicado')

    def test_el_estado_operativo_se_puede_completar(self):
        ficha = self.hacer_ficha(con_estado=False)

        response = self.completar(ficha, estado='cerrado')

        self.assertEqual(response.status_code, 200, response.content)
        ficha.refresh_from_db()
        self.assertEqual(ficha.operational_status.slug, 'cerrado')
        datos = response.json()
        self.assertIn('estado', datos['completado'])
        self.assertNotIn('estado', datos['faltan'])

    def test_un_estado_inventado_se_rechaza_en_la_puerta(self):
        ficha = self.hacer_ficha()

        response = self.completar(ficha, estado='volando')

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            '"estado" no es un estado valido.',
            response.json()['motivos'],
        )

    def test_el_envio_queda_registrado_con_la_ficha(self):
        ficha = self.hacer_ficha()

        self.completar(ficha)

        envio = Envio.objects.get()
        self.assertEqual(envio.estado, 'publicado')
        self.assertEqual(envio.negocio, ficha)
        self.assertEqual(envio.datos['ficha'], ficha.pk)

    # --------------------------- las fotos -----------------------------
    def test_completar_sin_foto_cuando_la_ficha_no_tiene_se_rechaza(self):
        """La obligacion sigue hasta que la ficha tenga UNA: sin foto
        no entra el envio —y con el, tampoco lo otro que traia—."""
        ficha = self.hacer_ficha()

        response = self.completar(ficha, fotos=0)

        self.assertEqual(response.status_code, 400)
        self.assertIn('foto', ' '.join(response.json()['motivos']).lower())
        self.assertEqual(
            BusinessContact.objects.filter(business=ficha).count(), 0,
        )

    def test_si_la_ficha_ya_tiene_foto_no_hace_falta_mandar(self):
        """Hasta que tenga foto, no mas alla: la que ya tiene una no
        bloquea completar sin mandar fotos nuevas."""
        ficha = self.hacer_ficha()
        BusinessImage.objects.create(business=ficha, image=_foto('ya.jpg'))

        response = self.completar(ficha, fotos=0)

        self.assertEqual(response.status_code, 200, response.content)

    def test_las_fotos_de_completar_se_anaden_a_las_que_ya_hay(self):
        ficha = self.hacer_ficha()
        for i in range(4):
            BusinessImage.objects.create(
                business=ficha, image=_foto('vieja%d.jpg' % i),
            )

        response = self.completar(ficha)          # una mas: 5 en total

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['imagenes'], 5)
        self.assertEqual(ficha.images.count(), 5)

    def test_completar_con_cinco_ya_no_admite_mas(self):
        ficha = self.hacer_ficha()
        for i in range(4):
            BusinessImage.objects.create(
                business=ficha, image=_foto('vieja%d.jpg' % i),
            )

        response = self.completar(ficha, fotos=2)  # 4 + 2 = 6

        self.assertEqual(response.status_code, 400)
        self.assertIn('5', ' '.join(response.json()['motivos']))
        self.assertEqual(ficha.images.count(), 4)

    # ------------------------ §11-i: el alcance ------------------------
    def test_una_ficha_de_otro_municipio_da_403(self):
        ficha = self.hacer_ficha(municipio='Santiago')

        response = self.completar(ficha)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(BusinessContact.objects.filter(business=ficha).count(), 0)
        # Tampoco se deja un renglon de auditoria: no es un dato malo, es
        # una llave que no abre.
        self.assertEqual(Envio.objects.count(), 0)

    def test_un_colaborador_sin_municipio_no_completa_nada(self):
        self.colaborador.municipio = ''
        self.colaborador.save()
        ficha = self.hacer_ficha()

        response = self.completar(ficha)

        self.assertEqual(response.status_code, 403)

    def test_una_ficha_inexistente_se_rechaza_en_la_puerta(self):
        response = self.completar(id_ficha=999999)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Esa ficha no existe.', response.json()['motivos'])
        self.assertEqual(Business.objects.count(), 0)

    def test_un_ficha_id_que_no_es_un_numero_no_pasa(self):
        response = self.completar(id_ficha='abc')

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            '"ficha" tiene que ser un numero.',
            response.json()['motivos'],
        )

    # ---------------------- poblar el formulario -----------------------
    def test_el_reporte_devuelve_la_ficha_para_rellenarla(self):
        ficha = self.hacer_ficha(telefono='809-111-2222')

        response = self.pedir_ficha(ficha)

        self.assertEqual(response.status_code, 200, response.content)
        datos = response.json()
        self.assertEqual(datos['id'], ficha.pk)
        self.assertEqual(datos['nombre'], 'Pan del Dia')
        self.assertEqual(datos['telefono'], '809-111-2222')
        self.assertEqual(datos['calle'], 'Calle 1 #10')
        self.assertEqual(datos['municipio'], 'Moca')
        self.assertEqual(datos['lat'], 19.3970)
        self.assertEqual(datos['categoria'], 'Panaderias')
        self.assertNotIn('telefono', datos['faltan'])
        self.assertIn('whatsapp', datos['faltan'])
        self.assertIn('horario', datos['faltan'])

    def test_el_reporte_devuelve_cuantas_fotos_tiene_la_ficha(self):
        """Con ese numero el formulario calcula cuanto le cabe: el
        techo son 5 en total, contando las que ya hay."""
        ficha = self.hacer_ficha()

        self.assertEqual(self.pedir_ficha(ficha).json()['imagenes'], 0)

        BusinessImage.objects.create(business=ficha, image=_foto())

        self.assertEqual(self.pedir_ficha(ficha).json()['imagenes'], 1)

    def test_el_formulario_devuelve_las_referencias(self):
        """Lo que ya se sabe del sitio no se pierde al reabrir la ficha:
        el formulario sale con lo que hay."""
        ficha = self.hacer_ficha()
        BusinessLocation.objects.filter(business=ficha).update(
            referencias='Frente a la parada del bus',
        )

        datos = self.pedir_ficha(ficha).json()

        self.assertEqual(datos['referencias'], 'Frente a la parada del bus')

    def test_al_completar_llena_las_referencias_que_faltaban(self):
        """Igual que la calle y el sector: solo si estaba vacio, y sale
        en «completado» para que se vea que el sistema lo acepto."""
        ficha = self.hacer_ficha()

        response = self.completar(ficha, referencias='Detras del parque')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('referencias', response.json()['completado'])
        self.assertEqual(
            BusinessLocation.objects.get(business=ficha).referencias,
            'Detras del parque',
        )

    def test_el_reporte_no_presta_fichas_de_otro_municipio(self):
        ficha = self.hacer_ficha(municipio='Santiago')

        response = self.pedir_ficha(ficha)

        self.assertEqual(response.status_code, 403)

    def test_una_ficha_inexistente_da_404(self):
        response = self.client.get(
            f'{PENDIENTES_URL}?ficha=999999',
            headers={'X-Colaborador-Token': self.colaborador.token},
        )

        self.assertEqual(response.status_code, 404)

    def test_un_ficha_id_basura_da_400(self):
        response = self.client.get(
            f'{PENDIENTES_URL}?ficha=abc',
            headers={'X-Colaborador-Token': self.colaborador.token},
        )

        self.assertEqual(response.status_code, 400)


class PortarDeDatosTests(TestCase):
    """`exportar_fichas` + `cargar_fichas` -> llevar los datos a produccion.

    Es la opcion B de R5: se importa aqui, se exporta un JSONL y en la
    otra base se carga con `cargar_fichas`. El formato no interesa — es
    interno—, si la promesa que hace la carga:

    * **no pisa**: lo que la base de destino ya tiene manda (§10-d);
    * **se puede correr dos veces** sin duplicar nada;
    * **una ficha creada a mano no se publica sola**, aunque el archivo
      diga que lo estaba (VISION.md);
    * **lo mal formado se rechaza en la puerta**, igual que lo que viene
      de OpenStreetMap — por eso los dos van por `masivo.Lote`.
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
        cls.tiendas = Category.objects.create(name='Tiendas', slug='tiendas')

    # ------------------------------ helpers ---------------------------
    def hacer(self, nombre, *, municipio='Moca', provincia='Espaillat',
              lat=19.3970, lng=-70.5270, telefono='809-555-1111',
              procedencia='importado', sin_publicar=False,
              sin_ubicacion=False):
        """Una ficha completa, como la dejaria el importador."""
        negocio = Business.objects.create(
            name=nombre,
            description='',
            category=self.tiendas,
            publication_status=(
                self.en_revision if sin_publicar else self.publicado
            ),
            operational_status=self.abierto,
            procedencia=procedencia,
        )
        if not sin_ubicacion:
            BusinessLocation.objects.create(
                business=negocio, street='Calle 1 #10',
                municipality=municipio, province=provincia,
                latitude=lat, longitude=lng,
            )
        if telefono:
            BusinessContact.objects.create(business=negocio, phone=telefono)
        BusinessHours.objects.create(
            business=negocio, day='Lunes',
            open_time='08:00', close_time='17:00',
        )
        return negocio

    def datos(self, nombre, **cambios):
        """Un registro completo del archivo, para los que se escriben a mano."""
        registro = {
            'nombre': nombre, 'telefono': '809-555-1111',
            'whatsapp': '', 'correo': '', 'web': '',
            'lat': 19.3970, 'lng': -70.5270,
            'municipio': 'Moca', 'provincia': 'Espaillat',
            'calle': 'Calle 1 #10', 'sector': '',
            'categoria': 'Tiendas', 'descripcion': '',
            'horario': [], 'estado': 'abierto', 'cerrado': False,
            'procedencia': 'importado',
        }
        registro.update(cambios)
        return registro

    def otro_municipio(self):
        """Una cabecera del padron que no sea Moca, con su propio punto."""
        return next(
            cab for cab in geografia.cabeceras()
            if geografia.normalizar(cab['municipio']) != 'moca'
        )

    def exportar(self, carpeta, **opciones):
        ruta = Path(carpeta) / 'fichas.ndjson.gz'
        salida = io.StringIO()
        call_command('exportar_fichas', str(ruta), stdout=salida, **opciones)
        return ruta, salida.getvalue()

    def cargar(self, ruta, **opciones):
        salida = io.StringIO()
        call_command('cargar_fichas', str(ruta), stdout=salida, **opciones)
        return salida.getvalue()

    def renglon(self, clave, valor):
        """Un renglon del RESULTADO, para compararlo sin pegarlo entero."""
        return '  %-22s %d' % (clave, valor)

    # --------------------------- el formato ---------------------------
    def test_una_linea_es_al_diccionario_planito_que_entra_por_osm(self):
        """Si el formato no fuera el mismo que `osm.a_datos`, la carga
        pasaria por otro sitio y no por la misma puerta y el mismo
        cruce."""
        datos = portar.datos_de(self.hacer('Pan del Dia'))

        regresado = portar.desde_linea(portar.a_linea(datos))

        self.assertEqual(regresado['nombre'], 'Pan del Dia')
        self.assertEqual(regresado['municipio'], 'Moca')
        self.assertEqual(regresado['categoria'], 'Tiendas')
        self.assertEqual(regresado['procedencia'], 'importado')
        self.assertEqual(regresado['estado'], 'abierto')
        self.assertEqual(regresado['lat'], 19.397)
        self.assertEqual(regresado['horario'][0]['day'], 'Lunes')
        self.assertIsInstance(regresado['horario'][0]['open'], datetime.time)

    def test_el_exportador_escribe_una_linea_por_ficha(self):
        self.hacer('Pan del Dia')
        self.hacer('Sin Ubicacion', sin_ubicacion=True)

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, texto = self.exportar(carpeta)
            with portar.abrir_texto(ruta, 'rt') as fh:
                lineas = [linea for linea in fh if linea.strip()]

        # Sin municipio no hay cabecera donde caer, y cargarla seria
        # crear una ficha que nadie puede buscar: se avisa, no se esconde.
        self.assertEqual(len(lineas), 1)
        self.assertIn('1 fichas escritas', texto)
        self.assertIn('1 sin municipio se quedaron fuera', texto)

    # ------------------------- lo que promete -------------------------
    def test_cargar_en_base_vacia_recrea_la_ficha_entera(self):
        self.hacer('Pan del Dia')

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = self.exportar(carpeta)
            Business.objects.all().delete()

            self.cargar(ruta)

        pan = Business.objects.get(name='Pan del Dia')

        self.assertEqual(pan.contact.phone, '809-555-1111')
        self.assertEqual(pan.location.municipality, 'Moca')
        self.assertEqual(float(pan.location.latitude), 19.397)
        self.assertEqual(pan.category.name, 'Tiendas')
        self.assertEqual(pan.operational_status.slug, 'abierto')
        self.assertEqual(pan.procedencia, 'importado')
        # El archivo no trae fotos y la imagen es obligatoria: la ficha
        # se carga entera pero espera en revision hasta que le pongan una.
        self.assertEqual(pan.publication_status.slug, 'en-revision')
        self.assertTrue(pan.hours.exists())

    def test_correr_la_carga_dos_veces_no_duplica(self):
        self.hacer('Pan del Dia')

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = self.exportar(carpeta)
            Business.objects.all().delete()

            self.cargar(ruta)
            segunda = self.cargar(ruta)

        self.assertEqual(Business.objects.filter(name='Pan del Dia').count(), 1)
        self.assertIn(self.renglon('creados', 0), segunda)
        self.assertIn(self.renglon('duplicados', 1), segunda)

    def test_no_pisa_lo_que_la_base_de_destino_ya_tiene(self):
        """§10-d: si aqui ya habia telefono, se queda el de aqui. El del
        archivo se ignora — no se sobrescribe nunca."""
        pan = self.hacer('Pan del Dia')

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = self.exportar(carpeta)
            pan.contact.phone = '809-999-9999'
            pan.contact.save()

            texto = self.cargar(ruta)

        pan = Business.objects.get(pk=pan.pk)
        self.assertEqual(Business.objects.count(), 1)
        self.assertEqual(pan.contact.phone, '809-999-9999')
        self.assertIn(self.renglon('creados', 0), texto)

    def test_el_telefono_del_archivo_completa_la_ficha_que_ya_esta(self):
        """Lo contrario: lo que falta aqui si se trae de alli."""
        pan = self.hacer('Pan del Dia')

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = self.exportar(carpeta)
            pan.contact.delete()

            texto = self.cargar(ruta)

        pan = Business.objects.get(pk=pan.pk)
        self.assertEqual(Business.objects.count(), 1)
        self.assertEqual(pan.contact.phone, '809-555-1111')
        self.assertIn(self.renglon('enriquecidos', 1), texto)

    def test_una_ficha_manual_no_se_publica_sola(self):
        """VISION.md: quien publica una ficha manual es el admin, aunque
        el archivo venga diciendo que estaba publicada."""
        self.hacer('La Receta', procedencia='manual', sin_publicar=True)

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = self.exportar(carpeta)
            Business.objects.all().delete()

            self.cargar(ruta)

        receta = Business.objects.get(name='La Receta')

        self.assertEqual(receta.publication_status.slug, 'en-revision')
        self.assertEqual(receta.procedencia, 'manual')

    def test_un_municipio_se_puede_dejar_fuera(self):
        """Para no tocar el que la base de destino ya tenia trabajado."""
        otra = self.otro_municipio()
        self.hacer('Pan del Dia')
        self.hacer(
            'Café del Pueblo', municipio=otra['municipio'],
            provincia=otra['provincia'], lat=otra['lat'], lng=otra['lng'],
        )

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = self.exportar(carpeta)
            Business.objects.all().delete()

            texto = self.cargar(ruta, omitir='Moca')

        self.assertEqual(Business.objects.filter(name='Pan del Dia').count(), 0)
        self.assertEqual(
            Business.objects.filter(name='Café del Pueblo').count(), 1)
        self.assertIn(self.renglon('omitidos', 1), texto)

    def test_un_punto_fuera_del_circulo_no_entra(self):
        """La misma puerta que lo que viene de OSM: el archivo no es un
        pase franco."""
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'fichas.ndjson'
            with portar.abrir_texto(ruta, 'wt') as fh:
                fh.write(portar.a_linea(self.datos('Lejos', lat=19.6000)) + '\n')

            texto = self.cargar(ruta)

        self.assertEqual(Business.objects.count(), 0)
        self.assertIn(self.renglon('rechazados', 1), texto)

    def test_excluir_un_municipio_lo_deja_fuera_del_archivo(self):
        """Produccion ya tiene Moca hecha a mano: exportarla solo puede
        estorbar (§10-d). Se queda fuera sin tocar nada de alla."""
        otra = self.otro_municipio()
        self.hacer('Pan del Dia')
        self.hacer(
            'Café del Pueblo', municipio=otra['municipio'],
            provincia=otra['provincia'], lat=otra['lat'], lng=otra['lng'],
        )

        with tempfile.TemporaryDirectory() as carpeta:
            ruta, texto = self.exportar(carpeta, excluir='Moca')
            with portar.abrir_texto(ruta, 'rt') as fh:
                lineas = [linea for linea in fh if linea.strip()]

        self.assertEqual(len(lineas), 1)
        self.assertIn('Café del Pueblo', lineas[0])
        self.assertIn('1 de municipios excluidos', texto)
        # La ficha de Moca sigue aqui, intacta: excluir es no exportarla.
        self.assertEqual(Business.objects.filter(name='Pan del Dia').count(), 1)


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class FiltroMunicipioEnAdminTests(TestCase):
    """La pantalla de Negocios del admin.

    Tiene que dejar filtrar por municipio en DOS pasos —provincia
    primero, municipio despues—: los 158 nombres en una sola lista no se
    recorren. Eso exige que cada municipio conserve su provincia, que es
    el dato con el que el segundo desplegable se recorta.
    """

    URL = '/admin/businesses/business/'

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')
        cls.tiendas = Category.objects.create(name='Tiendas', slug='tiendas')
        cls.visita = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')

    # ------------------------------ helpers ---------------------------

    def ficha(self, nombre, municipio, provincia, lat, lng):
        negocio = Business.objects.create(
            name=nombre, description='', category=self.tiendas,
            publication_status=self.publicado,
            operational_status=self.abierto, procedencia='importado')
        BusinessLocation.objects.create(
            business=negocio, municipality=municipio, province=provincia,
            latitude=lat, longitude=lng)

    def dos_municipios(self):
        self.ficha('Colmado La Esquina', 'Moca', 'Espaillat',
                   19.3970, -70.5270)
        self.ficha('Panadería La Peravia', 'Baní', 'Peravia',
                   18.2793, -70.3330)

    def lateral(self, respuesta):
        """Solo la columna de filtros, para no mezclarla con las filas."""
        texto = respuesta.content.decode()
        return texto[texto.index('id="changelist-filter"'):]

    def opcion(self, lateral, etiqueta):
        """El <option> entero de una etiqueta, para mirar sus atributos.

        El marcado va partido en varias lineas (valor, data-provincia y
        selected cada uno en la suya), asi que hacerle assert al texto
        visible no basta para comprobar bajo que provincia va.
        """
        patron = '<option\\b[^>]*>%s</option>' % re.escape(etiqueta)
        encontrada = re.search(patron, lateral)
        self.assertIsNotNone(
            encontrada, 'No aparece la opcion %r en el filtro' % etiqueta)
        return encontrada.group(0)

    # ------------------------------ tests -----------------------------

    def test_un_municipio_y_no_los_demas(self):
        self.dos_municipios()
        self.client.force_login(self.visita)

        respuesta = self.client.get(
            self.URL, {'location__municipality': 'Moca'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Colmado La Esquina')
        self.assertNotContains(respuesta, 'Panadería La Peravia')

    def test_los_municipios_salen_debajo_de_su_provincia(self):
        """Cada municipio conserva su provincia, que es lo que lo agrupa.

        Es el dato del que depende el segundo paso: si Moca perdiera su
        provincia, al elegir Espaillat no saldria. Ademas las provincias
        tienen que estar como desplegable propio, que es el primer paso.
        """
        self.dos_municipios()
        self.client.force_login(self.visita)

        lateral = self.lateral(self.client.get(self.URL))

        # Primer paso: las provincias, en su propio desplegable.
        self.assertIn('<option value="Espaillat">Espaillat</option>', lateral)
        self.assertIn('<option value="Peravia">Peravia</option>', lateral)

        # Segundo: cada municipio va con su provincia pegada, y las dos
        # tandas no se mezclan entre si.
        moca = self.opcion(lateral, 'Moca')
        bani = self.opcion(lateral, 'Baní')
        self.assertIn('data-provincia="Espaillat"', moca)
        self.assertIn('data-provincia="Peravia"', bani)

    def test_se_pueden_desmarcar_los_dos(self):
        self.dos_municipios()
        self.client.force_login(self.visita)

        lateral = self.lateral(
            self.client.get(self.URL, {'location__municipality': 'Moca'}))

        # Con uno elegido, el municipio sale marcado y sigue estando el
        # "Todos" para volver a la lista completa.
        self.assertIn('selected', self.opcion(lateral, 'Moca'))
        todos = self.opcion(lateral, 'Todos los municipios')
        self.assertIn('data-todos', todos)
        # Su value es la URL ya SIN el filtro: es como se quita.
        self.assertIn('value="?"', todos)


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class ColaboradorFormTests(TestCase):
    """Al crear un colaborador, el municipio sale anidado por provincia.

    Lo mismo que en la lista de Negocios: 158 nombres seguidos no se
    recorren, y el que ya sabe de que provincia es Moca no necesita que
    se lo repitan al lado.
    """

    URL = '/admin/businesses/colaborador/add/'

    @classmethod
    def setUpTestData(cls):
        cls.visita = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')

    def test_el_desplegable_anida_los_municipios_por_provincia(self):
        self.client.force_login(self.visita)

        html = self.client.get(self.URL).content.decode()

        self.assertIn('<optgroup label="Espaillat">', html)
        self.assertIn('<optgroup label="Peravia">', html)
        # El rotulo de la provincia antes que el municipio que lo sigue.
        self.assertLess(html.index('<optgroup label="Espaillat">'),
                        html.index('value="Moca"'))
        self.assertLess(html.index('<optgroup label="Peravia">'),
                        html.index('value="Baní"'))
        # Y lo que no pertenece a ningun grupo, fuera de los grupos.
        self.assertIn('— sin municipio —', html)


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class ColaboradorConteosTests(TestCase):
    """El listado de Colaboradores cuenta lo que ha hecho cada uno.

    Sin eso solo se ve quien ES, no quien TRABAJA: para repartir un
    municipio o para pillar a quien le estan rechazando todo hace falta
    saber cuantas correcciones ha mandado y cuando.
    """

    URL = '/admin/businesses/colaborador/'

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')
        cls.pedro = Colaborador.objects.create(
            nombre='Pedro', municipio='Moca')
        cls.maria = Colaborador.objects.create(
            nombre='Maria', municipio='Moca')

    def envios(self, colaborador, estados):
        for estado in estados:
            Envio.objects.create(colaborador=colaborador, estado=estado)

    def test_el_conteo_cuenta_lo_que_mando_y_enlaza_a_su_bandeja(self):
        """Y con el desglose: el total solo no distingue a quien le
        publican todo de a quien le rechazan todo."""
        self.envios(self.pedro, ['publicado', 'publicado', 'rechazado'])
        self.client.force_login(self.admin)

        html = self.client.get(self.URL).content.decode()

        self.assertIn(
            'title="Publicados: 2 · Pendientes: 0 · Rechazados: 1 · '
            'Duplicados: 0"',
            html,
        )
        # El conteo es un enlace a la auditoria ya filtrada por el.
        self.assertIn(
            '/admin/businesses/envio/?colaborador__id__exact=%d'
            % self.pedro.pk,
            html,
        )

    def test_al_que_no_ha_mandado_nada_le_sale_la_raya(self):
        self.client.force_login(self.admin)

        html = self.client.get(self.URL).content.decode()

        self.assertIn(
            '<a href="/admin/businesses/envio/?colaborador__id__exact=%d">'
            '—</a>' % self.maria.pk,
            html,
        )

    def test_el_conteo_se_puede_ordenar(self):
        self.envios(self.pedro, ['publicado', 'rechazado'])
        self.client.force_login(self.admin)

        # El indice de la columna no es fijo: la casilla de seleccion
        # se cuela la primera, asi que se le pregunta al listado.
        indice = self.client.get(self.URL).context['cl'].list_display.index(
            'correcciones')

        response = self.client.get(self.URL + '?o=-%d' % indice)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index('>Pedro<'), html.index('>Maria<'))

    def test_el_filtro_por_fecha_de_alta_restringe_el_listado(self):
        """Quien no existia en esa fecha no aparece: es la pregunta
        «¿quién es nuevo?»."""
        Colaborador.objects.filter(pk=self.maria.pk).update(
            creado_el=timezone.now() - datetime.timedelta(days=400),
        )
        self.client.force_login(self.admin)

        # Con hora y zona horaria, como arma sus enlaces el propio
        # admin: en una fecha plana Django interpreta la medianoche como
        # hora local naive y avisa con un RuntimeWarning.
        desde = urlencode({
            'creado_el__gte': timezone.now() - datetime.timedelta(days=1),
        })
        html = self.client.get(self.URL + '?' + desde).content.decode()

        self.assertIn('>Pedro<', html)
        self.assertNotIn('>Maria<', html)

    def test_el_filtro_por_fecha_del_ultimo_envio_restringe_tambien(self):
        """La otra pregunta: ¿quién acaba de trabajar?"""
        self.envios(self.pedro, ['publicado'])
        Colaborador.objects.filter(pk=self.pedro.pk).update(
            ultimo_envio=timezone.now())
        Colaborador.objects.filter(pk=self.maria.pk).update(
            ultimo_envio=timezone.now() - datetime.timedelta(days=400),
        )
        self.client.force_login(self.admin)

        desde = urlencode({
            'ultimo_envio__gte': timezone.now() - datetime.timedelta(days=1),
        })
        html = self.client.get(self.URL + '?' + desde).content.decode()

        self.assertIn('>Pedro<', html)
        self.assertNotIn('>Maria<', html)


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class BotonCorregirTests(TestCase):
    """De un aviso de la bandeja, al formulario del negocio.

    El aviso dice que algo esta mal pero no arrega nada: el arreglo es
    escribir el dato bueno en la ficha. El boton lleva directo a ESE
    formulario, sin pasar por la lista de Negocios.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')
        cls.tiendas = Category.objects.create(name='Tiendas', slug='tiendas')
        cls.negocio = Business.objects.create(
            name='Colmado La Esquina', description='', category=cls.tiendas,
            publication_status=cls.publicado,
            operational_status=cls.abierto, procedencia='importado')
        cls.correccion = Correction.objects.create(
            business=cls.negocio, campo='telefono',
            mensaje='El telefono que ponen no contesta: es 809-555-0000')
        cls.visita = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')

    def ruta_de_la_ficha(self):
        return f'/admin/businesses/business/{self.negocio.pk}/change/'

    def test_el_boton_de_dentro_de_la_correccion_abre_su_ficha(self):
        self.client.force_login(self.visita)

        html = self.client.get(
            f'/admin/businesses/correction/{self.correccion.pk}/change/'
        ).content.decode()

        self.assertIn(f'href="{self.ruta_de_la_ficha()}"', html)
        self.assertIn('Corregir', html)

    def test_el_boton_tambien_esta_en_el_listado(self):
        self.client.force_login(self.visita)

        html = self.client.get(
            '/admin/businesses/correction/').content.decode()

        self.assertIn(f'href="{self.ruta_de_la_ficha()}"', html)

    def test_el_alta_de_la_bandeja_no_se_cae_con_integrity_error(self):
        """El boton «Anadir» de Correcciones.

        get_form() hace exclude.extend(get_readonly_fields(...)), asi que
        si `business` fuese de solo lectura tambien en el alta el campo no
        llegaria al formulario, el INSERT guardaria un negocio NULL y la
        FK NOT NULL reventaria. Aqui se pide el formulario, se rellena y
        se guarda: tiene que salir una correccion creada.
        """
        self.client.force_login(self.visita)
        ruta = '/admin/businesses/correction/add/'

        formulario = self.client.get(ruta)
        self.assertEqual(formulario.status_code, 200)
        # El desplegable del negocio tiene que estar en el formulario.
        self.assertContains(formulario, 'id_business')

        response = self.client.post(ruta, {
            'business': self.negocio.pk,
            'campo': 'direccion',
            'mensaje': 'La calle esta mal escrita: es J. Sanchez',
            'estado': 'pendiente',
            'nota_admin': '',
            'resolved_at_0': '',
            'resolved_at_1': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Correction.objects.filter(
            business=self.negocio, campo='direccion').exists())

    def test_leyendo_la_correccion_sigue_todo_de_solo_lectura(self):
        """El arreglo del alta no toca la vista de lectura: ahi el aviso
        del visitante se MUESTRA pero no se edita."""
        self.client.force_login(self.visita)

        html = self.client.get(
            f'/admin/businesses/correction/{self.correccion.pk}/change/'
        ).content.decode()

        self.assertIn('El telefono que ponen no contesta: es 809-555-0000',
                      html)
        self.assertNotIn('<textarea name="mensaje"', html)
        self.assertNotIn('<select name="business"', html)


class EstadoEfectivoTests(TestCase):
    """La etiqueta de estado tiene que ser la misma en todas partes.

    La rejilla (BusinessCard), el modal (BusinessModal) y la ficha en
    /business/:slug (BusinessDetail) pintan lo que devuelve la API.
    Antes la ficha se quedaba con el estado DECLARADO en la base y las
    otras dos con el CALCULADO con el horario de hoy, con lo que un
    mismo negocio podia salir "Abierto" en una y "Cerrado" en otra.
    Y el de horario se escribe "Por horario", igual que en la app de
    Android.
    """

    @property
    def hoy(self):
        """Día de HOY según la zona del proyecto (America/Santo_Domingo),
        no la del host: en Render el servidor vive en UTC y el día local
        puede ser todavía el anterior."""
        return ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes',
                'Sábado', 'Domingo'][timezone.localdate().weekday()]

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.categoria = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')

    def negocio(self, name, **horario):
        """Un negocio publicado; ``horario`` son los datos de HOY."""
        biz = Business.objects.create(
            name=name,
            description=f'Descripcion de {name}',
            short_description=name,
            category=self.categoria,
            publication_status=self.publicado,
            operational_status=self.abierto,
        )
        # Ubicacion de Moca (fase): el listado recorta por provincia.
        BusinessLocation.objects.create(
            business=biz, municipality='Moca', province='Espaillat',
            latitude=MOCA_LAT, longitude=MOCA_LNG,
        )
        if horario:
            BusinessHours.objects.create(business=biz, day=self.hoy, **horario)
        return biz

    def estado(self, nombre):
        """Lo que dice la API de ficha de ese negocio."""
        return self.client.get(f'{BUSINESSES_URL}{nombre.slug}/').json()

    def test_un_horario_que_ya_paso_dice_por_horario(self):
        """Tiene horario hoy pero ya cerro: ni abierto ni sin estado.

        La ventana se pone 3 y 2 horas por detras de la hora actual,
        asi que esta atras en cualquier hora del dia y el test no se
        puede caer por la hora en que se ejecute.
        """
        desde = timezone.localtime(
            timezone.now() - datetime.timedelta(hours=3)).time()
        hasta = timezone.localtime(
            timezone.now() - datetime.timedelta(hours=2)).time()
        biz = self.negocio('Panaderia De La Manana',
                           open_time=desde, close_time=hasta)

        data = self.estado(biz)

        self.assertEqual(data['effective_status'], 'por-horario')
        self.assertEqual(data['effective_status_name'], 'Por horario')

    def test_un_dia_marcado_como_cerrado_es_cerrado(self):
        biz = self.negocio('Cafeteria Cerrada', is_closed=True)

        data = self.estado(biz)

        self.assertEqual(data['effective_status'], 'cerrado')
        self.assertEqual(data['effective_status_name'], 'Cerrado')

    def test_sin_horario_hoy_manda_lo_que_dice_la_base(self):
        """No hay datos de hoy: no se inventa, se usa el declarado."""
        biz = self.negocio('Sin Horario')

        data = self.estado(biz)

        self.assertEqual(data['effective_status'], 'abierto')
        self.assertEqual(data['effective_status_name'], 'Abierto')

    def test_el_listado_y_la_ficha_dicen_lo_mismo(self):
        """Lo que pinta la tarjeta y lo que pinta la ficha es la MISMA
        pareja de campos: no pueden contradecirse."""
        desde = timezone.localtime(
            timezone.now() - datetime.timedelta(hours=3)).time()
        hasta = timezone.localtime(
            timezone.now() - datetime.timedelta(hours=2)).time()
        biz = self.negocio('Panaderia Sin Luz',
                           open_time=desde, close_time=hasta)

        lista = self.client.get(BUSINESSES_URL).json()['results']
        ficha = self.estado(biz)

        self.assertEqual(
            (lista[0]['effective_status'], lista[0]['effective_status_name']),
            (ficha['effective_status'], ficha['effective_status_name']),
        )


class EstadoUsaElRelojDelProyectoTests(TestCase):
    """El estado abierto/cerrado debe salir de la hora de República
    Dominicana, no de la del servidor.

    En Render el host vive en UTC: con ``date.today()``/``datetime.now()``
    el estado salía desfasado 4-5 horas (un negocio abierto a las 10 p. m.
    salía "cerrado" y uno cerrado a las 10 a. m. salía "abierto") y entre
    medianoche y las 4 a. m. hasta el día de la semana salía mal. Los tests
    anteriores no lo pillaban porque construían la ventana con el MISMO
    reloj equivocado que usaba el código: pasaban en cualquier host.

    Aquí el instante se congela con mock sobre ``timezone.now()``, del que
    derivan ``localtime()``/``localdate()`` — justo los que ahora usa el
    código. El negocio se declara 'cerrado' para que el resultado sólo
    pueda venir del cálculo con horario.
    """

    # Miércoles 28 de octubre de 2026, 02:00 UTC = MARTES 27, 10:00 p. m.
    # en República Dominicana (UTC-4). Con America/Bogota saldría 9:00 p. m.
    # y con el reloj del host (UTC) el día 28.
    INSTANTE = datetime.datetime(
        2026, 10, 28, 2, 0, tzinfo=datetime.timezone.utc)

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.categoria = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.cerrado = OperationalStatus.objects.create(
            name='Cerrado', slug='cerrado')

    def negocio(self, dia, **horas):
        biz = Business.objects.create(
            name=f'Negocio De {dia}',
            description=f'Descripcion de {dia}',
            short_description=dia,
            category=self.categoria,
            publication_status=self.publicado,
            operational_status=self.cerrado,
        )
        BusinessHours.objects.create(business=biz, day=dia, **horas)
        return biz

    def test_la_fecha_y_la_hora_son_las_de_republica_dominicana(self):
        with patch('django.utils.timezone.now', return_value=self.INSTANTE):
            # En UTC todavía es el 28; en RD ya es el 27.
            self.assertEqual(timezone.localdate(),
                             datetime.date(2026, 10, 27))
            # 10:00 p. m. en RD — America/Bogota daría 9:00 p. m.
            self.assertEqual(timezone.localtime().time(),
                             datetime.time(22, 0))

    def test_abierto_a_las_diez_de_la_noche_aunque_en_utc_ya_amochezca(self):
        """Horario de martes 8:00-23:00: a las 10 p. m. del martes (la
        hora real del país) está ABIERTO. Con el reloj UTC el código miraba
        el miércoles, no encontraba horario y devolvía el declarado."""
        biz = self.negocio(
            'Martes',
            open_time=datetime.time(8, 0), close_time=datetime.time(23, 0))

        with patch('django.utils.timezone.now', return_value=self.INSTANTE):
            self.assertEqual(compute_operational_status(biz), 'abierto')

    def test_no_mira_el_horario_del_dia_siguiente(self):
        """Horario sólo del miércoles (el día UTC): el país todavía es
        martes y el negocio no tiene horario de hoy, así que manda el
        declarado. Antes salía 'abierto' a las 10 p. m. del martes."""
        biz = self.negocio(
            'Miércoles',
            open_time=datetime.time(0, 0), close_time=datetime.time(23, 59))

        with patch('django.utils.timezone.now', return_value=self.INSTANTE):
            self.assertEqual(compute_operational_status(biz), 'cerrado')


class ElListadoNoConsultaPorNegocioTests(TestCase):
    """El listado no debe hacer queries proporcionales a los negocios.

    Medido antes de arreglarlo: la pagina de 12 hacia 24 queries, todas de
    ``hours``. El queryset YA venia con ``prefetch_related('hours')``, pero
    ``compute_operational_status`` llamaba a ``business.hours.filter(day=...)``:
    ``.filter()`` descarta el caché de prefetch y consulta por cada objeto. Y
    lo hacía DOS veces, porque ``effective_status`` y ``effective_status_name``
    llaman ambas a la misma función.

    La garantía que se pone aqui es que el coste sea CONSTANTE: una pagina de
    8 debe costar lo mismo que una de 4. Un N+1 que se reintroduzca rompe esa
    igualdad, y el mensaje del test trae los dos numeros.
    """

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.categoria = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.cerrado = OperationalStatus.objects.create(
            name='Cerrado', slug='cerrado')

    def negocio(self, i):
        biz = Business.objects.create(
            name=f'Negocio {i}',
            description=f'Descripcion del negocio {i}',
            short_description=f'Desc {i}',
            category=self.categoria,
            publication_status=self.publicado,
            operational_status=self.cerrado,
        )
        # Moca, Espaillat: provincia de FASE1. Sin ubicacion en fase el
        # listado recorta el negocio y el test mediria una pagina vacia.
        BusinessLocation.objects.create(
            business=biz, municipality='Moca', province='Espaillat',
            latitude=19.3970, longitude=-70.5270,
        )
        BusinessHours.objects.create(
            business=biz, day='Lunes',
            open_time=datetime.time(8, 0), close_time=datetime.time(18, 0))
        return biz

    def queries_de_la_pagina(self, cantidad):
        """Crea ``cantidad`` negocios y devuelve cuantas queries hizo el
        ENDPOINT real al servir esa pagina (no el serializer suelto)."""
        for i in range(cantidad):
            self.negocio(i)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                BUSINESSES_URL + f'?page_size={cantidad}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), cantidad)
        return len(queries.captured_queries)

    def test_el_coste_no_crece_con_el_tamano_de_la_pagina(self):
        # Calentamiento: la PRIMERA peticion del proceso crea la fila del
        # contador de uso (INSERT en uso_usodiario) y cachea content types,
        # asi que trae una query mas que no tiene nada que ver con el
        # listado. Sin esta llamada previa la comparacion media el analitico.
        self.client.get(BUSINESSES_URL + '?page_size=1')

        cuatro = self.queries_de_la_pagina(4)
        ocho = self.queries_de_la_pagina(8)

        self.assertEqual(
            cuatro, ocho,
            f'La pagina de 4 hizo {cuatro} queries y la de 8 {ocho}: el '
            'coste crece con el numero de negocios (N+1).')

    def test_no_necesita_mas_queries_que_relaciones_por_negocio(self):
        """Cota absoluta, por si las dos paginas coincidieran por casualidad:
        8 negocios con location, contact, hours e images no pueden pedir ni
        una query por negocio."""
        self.assertLessEqual(self.queries_de_la_pagina(8), 10)


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class EnlaceLevantamientoTests(TestCase):
    """El enlace a la herramienta de campo, dentro del admin.

    El colaborador no entra aqui, pero quien lo da de alta si: el
    enlace y su boton de compartir estan en el inicio (para pasarlo sin
    buscar) y en la ficha del colaborador (junto al token que ya se le
    esta entregando). Sin JS el enlace sigue siendo un <a> clicable.
    """

    ENLACE = 'https://buscandoando.onrender.com/levantamiento'

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')
        cls.colaborador = Colaborador.objects.create(
            nombre='Herling', municipio='Moca')

    def test_en_el_inicio(self):
        self.client.force_login(self.admin)

        html = self.client.get('/admin/').content.decode()

        self.assertIn(f'href="{self.ENLACE}"', html)
        self.assertIn('data-ba-compartir', html)

    def test_en_la_ficha_del_colaborador(self):
        self.client.force_login(self.admin)

        html = self.client.get(
            f'/admin/businesses/colaborador/{self.colaborador.pk}/change/'
        ).content.decode()

        self.assertIn(f'href="{self.ENLACE}"', html)
        self.assertIn('data-ba-compartir', html)

    def test_el_boton_tiene_su_javascript_cargado(self):
        """El panel sin JS deja el enlace, pero no el compartir."""
        self.client.force_login(self.admin)

        html = self.client.get('/admin/').content.decode()

        self.assertIn('admin/js/buscandoando_share.js', html)


class IPDelEnvioTests(SimpleTestCase):
    """La IP del Envio se toma de donde la declaro el ULTIMO proxy.

    X-Forwarded-For se construye de izquierda a derecha: lo primero lo
    teclea el CLIENTE —spoofable: quien manda el envio podia firmar la
    IP que quisiera— y cada proxy anade el suyo al final. Antes se leia
    la primera entrada (hallado en la auditoria del 19/oct de 2026).
    """

    def test_la_ip_es_la_ultima_de_la_cadena(self):
        peticion = RequestFactory().get(
            '/', HTTP_X_FORWARDED_FOR='9.9.9.9, 8.8.8.8')

        self.assertEqual(_ip(peticion), '8.8.8.8')

    def test_entradas_invalidas_se_de_lado_y_sigue_la_anterior(self):
        peticion = RequestFactory().get(
            '/', HTTP_X_FORWARDED_FOR='no-es-ip, 9.9.9.9, 8.8.8.8')

        self.assertEqual(_ip(peticion), '8.8.8.8')

    def test_cf_connecting_ip_manda_sobre_la_cadena(self):
        """Detras de Cloudflare, solo el puede escribir esa cabecera:
        si llega, es la del visitante aunque la cadena diga otra cosa."""
        peticion = RequestFactory().get(
            '/',
            HTTP_CF_CONNECTING_IP='203.0.113.9',
            HTTP_X_FORWARDED_FOR='9.9.9.9, 8.8.8.8')

        self.assertEqual(_ip(peticion), '203.0.113.9')

    def test_cf_connecting_ip_invalida_se_descarta(self):
        peticion = RequestFactory().get(
            '/',
            HTTP_CF_CONNECTING_IP='no-es-ip',
            HTTP_X_FORWARDED_FOR='9.9.9.9, 8.8.8.8')

        self.assertEqual(_ip(peticion), '8.8.8.8')

    def test_sin_cadena_se_usa_remote_addr(self):
        peticion = RequestFactory().get('/')

        self.assertEqual(_ip(peticion), '127.0.0.1')


def _datos_del_formulario_admin(client, url):
    """POST valido del panel: valores que el propio formulario pinta.

    Se arranca de lo que Django renderiza — incluidos los management
    forms de los inlines, que van a cero filas — para no inventarse
    campos: el 302 tiene que depender de lo que se esta probando, no
    de un campo que falte. Lo comparten la clase del slug y la de los
    filtros del listado.
    """
    pagina = client.get(url)
    if pagina.status_code != 200:
        raise AssertionError('el panel no abrio %s (%s)' % (
            url, pagina.status_code))
    form = pagina.context['adminform'].form
    datos = {}
    for nombre in form.fields:
        valor = form[nombre].value()
        if valor is None:
            continue
        if isinstance(valor, bool):
            if valor:
                datos[nombre] = 'on'
        elif isinstance(valor, (list, tuple)):
            datos[nombre] = [str(v) for v in valor]
        else:
            datos[nombre] = str(valor)
    for inline in pagina.context['inline_admin_formsets']:
        prefijo = inline.formset.prefix
        datos['%s-TOTAL_FORMS' % prefijo] = '0'
        datos['%s-INITIAL_FORMS' % prefijo] = '0'
    datos['_save'] = 'Guardar'
    return datos


class SlugEditableConRedireccion(TestCase):
    """Slug editable en el panel con redireccion 301 del slug anterior.

    Tres piezas que tienen que ir juntas: el modelo guarda el slug
    anterior (``SlugAntiguo``), el formulario del admin lo acepta — con
    acentos, que la base los guarda — y la API publica redirige al slug
    actual en vez de dar 404. Lo no publicado sigue siendo 404 por
    todas las vias: el historial no filtra nada.
    """

    CAMBIO = '/admin/businesses/business/%d/change/'

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.revision = PublicationStatus.objects.create(
            name='En Revision', slug='en-revision')
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')
        cls.restaurantes = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.admin = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')

    def ficha(self, nombre, estado=None):
        return Business.objects.create(
            name=nombre,
            description='Descripcion de %s' % nombre,
            short_description='%s: descripcion corta.' % nombre,
            category=self.restaurantes,
            publication_status=estado or self.publicado,
            operational_status=self.abierto,
        )

    # --- el modelo: el slug anterior queda registrado --------------------

    def test_al_cambiar_el_slug_el_anterior_queda_registrado(self):
        ficha = self.ficha('Panaderia Luna')
        viejo = ficha.slug

        ficha.slug = 'panaderia-luna-centro'
        ficha.save()

        fila = SlugAntiguo.objects.get(slug=viejo)
        self.assertEqual(fila.business_id, ficha.pk)
        # El actual no puede quedar en el historial: el vivo manda.
        self.assertFalse(
            SlugAntiguo.objects.filter(slug=ficha.slug).exists())

    def test_si_un_negocio_toma_un_slug_de_anteano_se_borra_su_registro(self):
        primero = self.ficha('Primera')
        primero.slug = 'libre'
        primero.save()                      # historial: 'primera' -> primero
        segundo = self.ficha('Segunda')
        segundo.slug = 'primera'            # segundo toma ese slug
        segundo.save()

        self.assertFalse(SlugAntiguo.objects.filter(slug='primera').exists())

    # --- el formulario del panel ----------------------------------------

    def test_el_panel_pinta_el_slug_como_campo_editable(self):
        ficha = self.ficha('Panaderia Luna')
        self.client.force_login(self.admin)

        respuesta = self.client.get(self.CAMBIO % ficha.pk)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="slug"')
        # El help_text avisa de la consecuencia de cambiarlo.
        self.assertContains(respuesta, 'redirige')

    def _datos_del_formulario(self, url):
        """El POST de verdad; la logica vive en el helper de modulo."""
        return _datos_del_formulario_admin(self.client, url)

    def test_guardar_el_formulario_cambia_el_slug_y_conserva_el_anterior(self):
        ficha = self.ficha('Panaderia Luna')
        self.client.force_login(self.admin)
        url = self.CAMBIO % ficha.pk
        datos = self._datos_del_formulario(url)
        datos['slug'] = 'panaderia-luna-centro'

        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 302)
        ficha.refresh_from_db()
        self.assertEqual(ficha.slug, 'panaderia-luna-centro')
        self.assertTrue(
            SlugAntiguo.objects.filter(slug='panaderia-luna',
                                       business=ficha).exists())

    def test_un_slug_con_tildes_no_es_error_de_validacion(self):
        """Django valida los SlugField en ASCII: este form no puede.

        Hay miles de slugs con tildes en la base; sin allow_unicode el
        panel no dejaria guardar ninguno de esos negocios.
        """
        ficha = self.ficha('Cafeteria El Paraiso')
        self.client.force_login(self.admin)
        url = self.CAMBIO % ficha.pk
        datos = self._datos_del_formulario(url)
        datos['slug'] = 'cafetería-el-paraíso'

        respuesta = self.client.post(url, datos)

        errores = (respuesta.context['adminform'].form.errors
                   if getattr(respuesta, 'context', None) else {})
        self.assertEqual(respuesta.status_code, 302,
                         'errores del form: %s' % errores)
        ficha.refresh_from_db()
        self.assertEqual(ficha.slug, 'cafetería-el-paraíso')

    def test_un_slug_que_ya_es_de_otro_negocio_no_se_guarda(self):
        self.ficha('Panaderia Luna')        # se queda con 'panaderia-luna'
        otra = self.ficha('Otra Panaderia')
        self.client.force_login(self.admin)
        url = self.CAMBIO % otra.pk
        datos = self._datos_del_formulario(url)
        datos['slug'] = 'panaderia-luna'

        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context['adminform'].form.errors
        self.assertIn('slug', errores)
        otra.refresh_from_db()
        self.assertEqual(otra.slug, 'otra-panaderia')

    # --- la API publica -------------------------------------------------

    def test_la_api_por_el_slug_viejo_redirige_al_actual(self):
        ficha = self.ficha('Panaderia Luna')
        viejo = ficha.slug
        ficha.slug = 'panaderia-luna-centro'
        ficha.save()

        respuesta = self.client.get('/api/businesses/%s/' % viejo)

        self.assertEqual(respuesta.status_code, 301)
        self.assertEqual(respuesta['Location'],
                         '/api/businesses/panaderia-luna-centro/')
        # La peticion de despues (con el slug bueno) sirve la ficha.
        self.assertEqual(
            self.client.get(
                '/api/businesses/panaderia-luna-centro/').status_code, 200)

    def test_la_api_por_el_slug_viejo_de_una_ficha_sin_publicar_es_404(self):
        ficha = self.ficha('Ideas Nuevas', estado=self.revision)
        viejo = ficha.slug
        ficha.slug = 'ideas-nuevas-nuevo'
        ficha.save()

        self.assertEqual(
            self.client.get('/api/businesses/%s/' % viejo).status_code, 404)


class FiltrosDelListadoSeConservan(TestCase):
    """Volver un nivel atras no pierde los filtros del listado.

    Desde un listado filtrado, Django enlaza cada fila con
    ``?_changelist_filters=...`` (la query de origen codificada una vez
    mas) y el tag ``add_preserved_filters`` la reexpande en la query de
    verdad cuando el destino es ese changelist. Se perdia en dos
    sitios:

    * la miga «Negocios» del formulario de cambio, que apuntaba al
      changelist pelado — el fallo que se reporto: guardar y volver
      atras reestablecia la busqueda y los filtros;
    * el redirect tras «Guardar», que Django ya hacia bien y aqui
      queda cubierto para que nadie lo rompa.
    """

    CAMBIO = '/admin/businesses/business/%d/change/'

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado')
        cls.abierto = OperationalStatus.objects.create(
            name='Abierto', slug='abierto')
        cls.restaurantes = Category.objects.create(
            name='Restaurantes', slug='restaurantes')
        cls.admin = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'x')
        cls.ficha = Business.objects.create(
            name='Panaderia Luna', description='Descripcion',
            category=cls.restaurantes, publication_status=cls.publicado,
            operational_status=cls.abierto)

    def _con_filtros(self, filtros):
        """La URL del cambio tal como la enlaza el listado filtrado."""
        return (self.CAMBIO % self.ficha.pk) + '?' + urlencode(
            {'_changelist_filters': urlencode(filtros)})

    def test_tras_guardar_vuelve_al_listado_con_los_filtros(self):
        self.client.force_login(self.admin)
        url = self._con_filtros({'q': 'Pan'})
        datos = _datos_del_formulario_admin(self.client, url)

        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/admin/businesses/business/?', respuesta['Location'])
        self.assertIn('q=Pan', respuesta['Location'])

    def test_la_miga_al_listado_conserva_los_filtros(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(self._con_filtros({'q': 'Pan'}))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta, 'href="/admin/businesses/business/?q=Pan"')
