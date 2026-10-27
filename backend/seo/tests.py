"""Tests del modulo SEO (DISENO 15).

Lo que se prueba es lo que el publico y los buscadores ven: metas por
ruta (por defecto y personalizadas a mano) y robots.txt (fila de la
base con el fichero del build de respaldo). El panel del admin se
prueba en lo que exige su razon de ser: que solo el staff entra y que
lo guardado a mano se sirve tal cual.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from seo.models import SeoRuta, SeoRobots

# El admin maquilla las hojas con el storage con manifest, que solo
# resuelve despues de `collectstatic`: en los tests no hay manifest y la
# pagina de admin ni llegaria a pintarse. Mismo tramite que en
# businesses/tests.py (STATIC_SIN_MANIFEST). Aquí cuela porque el CI hace
# un clon limpio y allí tampoco existen ni el manifest ni el dist/ de
# React (los dos en .gitignore): las 3 clases de este fichero pintan el
# admin y sin esto revientan con "Missing staticfiles manifest entry".
STATIC_SIN_MANIFEST = {
    **settings.STORAGES,
    'staticfiles': {'BACKEND':
                    'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=STATIC_SIN_MANIFEST)
class MetasPorRutaTest(TestCase):
    """La portada y la herramienta de campo, con y sin fila propia."""

    def test_portada_con_metas_por_defecto(self):
        """La siembra guarda las metas de siempre: nada cambia hoy."""
        html = self.client.get('/').content.decode()
        self.assertIn('BuscandoAndo - Encuentra negocios en República '
                      'Dominicana</title>', html)
        self.assertIn('<meta name="robots" content="index,follow" />', html)

    def test_portada_personalizada_manda_sobre_el_codigo(self):
        """Lo que se cambie a mano rige sin desplegar."""
        fila = SeoRuta.objects.get(ruta='')
        fila.titulo = 'Titulo a mano'
        fila.descripcion = 'Descripcion a mano.'
        fila.noindex = True
        fila.save()

        html = self.client.get('/').content.decode()
        self.assertIn('<title>Titulo a mano</title>', html)
        self.assertIn('Descripcion a mano.', html)
        self.assertIn('<meta name="robots" content="noindex,nofollow" />',
                      html)

    def test_levantamiento_con_fila_propia(self):
        fila = SeoRuta.objects.get(ruta='levantamiento')
        fila.titulo = 'Captura de campo'
        fila.save()

        html = self.client.get('/levantamiento').content.decode()
        self.assertIn('<title>Captura de campo</title>', html)
        # Sigue sin indexarse: la herramienta no tiene enlace publico.
        self.assertIn('<meta name="robots" content="noindex,nofollow" />',
                      html)

    def test_imagen_vacia_cae_en_la_og_del_sitio(self):
        fila = SeoRuta.objects.get(ruta='')
        fila.imagen = ''
        fila.save()
        html = self.client.get('/').content.decode()
        self.assertIn('<meta property="og:image" content="%s/og.png" />'
                      % self._sitio(), html)

    def test_imagen_relativa_se_vuelve_absoluta(self):
        fila = SeoRuta.objects.get(ruta='')
        fila.imagen = '/og2.png'
        fila.save()
        html = self.client.get('/').content.decode()
        self.assertIn('<meta property="og:image" content="%s/og2.png" />'
                      % self._sitio(), html)

    @staticmethod
    def _sitio():
        from django.conf import settings
        return settings.SITIO_URL.rstrip('/')


class RobotsTxtTest(TestCase):
    """El robots.txt sirve la configuracion; sin ella, el build."""

    def test_sirve_el_build_por_defecto(self):
        respuesta = self.client.get('/robots.txt')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('text/plain', respuesta['Content-Type'])
        contenido = respuesta.content.decode()
        self.assertIn('User-agent: *', contenido)
        self.assertIn('Sitemap: ', contenido)

    def test_la_fila_de_la_base_manda(self):
        fila = SeoRobots.cargar()
        self.assertIsNotNone(fila, 'La migracion siembra la fila unica')
        fila.contenido = 'User-agent: *\nDisallow: /nada/\n'
        fila.save()

        contenido = self.client.get('/robots.txt').content.decode()
        self.assertIn('Disallow: /nada/', contenido)
        self.assertNotIn('Disallow: /admin/', contenido)

    def test_fila_en_blanco_vuelve_al_build(self):
        fila = SeoRobots.cargar()
        fila.contenido = '   \n'
        fila.save()

        contenido = self.client.get('/robots.txt').content.decode()
        self.assertIn('Disallow: /admin/', contenido)


class PanelSeoTest(TestCase):
    """El panel del admin: para el staff, y con las piezas reales."""

    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            'seo_admin', 'seo@example.com', 'clave-seo-123')
        self.client.force_login(usuario)

    # La corrección va NIVEL MÉTODO, no nivel de clase. A diferencia de
    # businesses/tests.py (donde pinta el admin en el setUp y basta
    # con la clase), aquí hay tests que no pintan ningún template y el
    # decorador de clase no llega a los atributos que se crean después
    # de la decoración: test_cambiar_las_metas_desde_el_admin pinta la
    # portada y se quedaría sin la corrección.
    @override_settings(STORAGES=STATIC_SIN_MANIFEST)
    def test_panel_ensena_metas_robots_y_sitemap(self):
        respuesta = self.client.get(reverse('admin_seo'))
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('Metas por ruta', html)
        self.assertIn('robots.txt', html)
        self.assertIn('sitemap.xml', html)
        # La fila de la portada enlaza a su edicion (esta sembrada).
        fila = SeoRuta.objects.get(ruta='')
        self.assertIn(reverse('admin:seo_seoruta_change', args=[fila.pk]),
                      html)

    def test_solo_staff_entra(self):
        self.client.logout()
        respuesta = self.client.get(reverse('admin_seo'))
        # admin_view manda al login del admin.
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/admin/login/', respuesta['Location'])

    @override_settings(STORAGES=STATIC_SIN_MANIFEST)
    def test_cambiar_las_metas_desde_el_admin(self):
        fila = SeoRuta.objects.get(ruta='')
        respuesta = self.client.post(
            reverse('admin:seo_seoruta_change', args=[fila.pk]),
            {'ruta': '', 'titulo': 'Titulo nuevo', 'descripcion': 'Desc.',
             'imagen': '', 'noindex': 'on', '_save': 'Guardar'})
        self.assertEqual(respuesta.status_code, 302)
        fila.refresh_from_db()
        self.assertEqual(fila.titulo, 'Titulo nuevo')
        self.assertTrue(fila.noindex)
        # Y la portada lo sirve ya.
        html = self.client.get('/').content.decode()
        self.assertIn('<title>Titulo nuevo</title>', html)
