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

from django.test import TestCase
from django.utils import timezone

from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from .models import Business

BUSINESSES_URL = '/api/businesses/'
FEATURED_BY_SEARCH_URL = '/api/businesses/featured-by-search/'


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
