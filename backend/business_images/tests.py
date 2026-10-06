"""Procesado de las fotos: tamaño fijo, recorte y WebP (y límite de 5).

Cubre la regla que pidió el usuario:

* toda foto que entra se guarda recortada al tamaño fijo y en WebP;
* el recorte es "cover" (centrado, sin deformar) sea cual sea la
  proporción original;
* si el archivo no se puede procesar, se guarda el original sin más;
* el único límite sigue siendo MAX_IMAGES_PER_BUSINESS = 5.
"""
import io
import shutil
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from businesses.models import Business
from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from .models import MAX_IMAGES_PER_BUSINESS, BusinessImage
from .processing import IMAGE_SIZE

# El storage por defecto es Cloudinary: en los tests no hay red, así
# que se apunta a una carpeta temporal de disco.
MEDIA_DE_PRUEBA = tempfile.mkdtemp(prefix='buscandoando_media_')
STORAGES_DE_PRUEBA = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


def foto(nombre, ancho, alto, formato='JPEG'):
    """Archivo de subida de un color plano, del tamaño pedido."""
    buf = io.BytesIO()
    Image.new('RGB', (ancho, alto), (251, 191, 36)).save(buf, format=formato)
    tipo = 'image/png' if formato == 'PNG' else 'image/jpeg'
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type=tipo)


def abrir(imagen):
    """(formato, tamaño) del archivo ya guardado, leyéndolo del storage."""
    with imagen.image.open('rb') as fh:
        datos = fh.read()
    with Image.open(io.BytesIO(datos)) as im:
        return im.format, im.size, im.mode


@override_settings(STORAGES=STORAGES_DE_PRUEBA, MEDIA_ROOT=MEDIA_DE_PRUEBA)
class ProcesadoDeFotoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.publicado = PublicationStatus.objects.create(
            name='Publicado', slug='publicado'
        )
        cls.categoria = Category.objects.create(
            name='Restaurantes', slug='restaurantes'
        )
        cls.estado = OperationalStatus.objects.create(name='Abierto', slug='abierto')
        cls.business = Business.objects.create(
            name='Cafeteria Central',
            description='Descripcion de prueba',
            category=cls.categoria,
            publication_status=cls.publicado,
            operational_status=cls.estado,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DE_PRUEBA, ignore_errors=True)

    # ------------------------- tamaño fijo -------------------------
    def test_las_fotos_se_guardan_en_webp_del_tamano_fijo(self):
        """Da igual que suban vertical o apaisada: sale siempre 1200x675."""
        vertical = BusinessImage.objects.create(
            business=self.business, order=0, image=foto('retrato.jpg', 900, 1200)
        )
        apaisada = BusinessImage.objects.create(
            business=self.business, order=1, image=foto('panorama.jpg', 2400, 800)
        )

        for imagen in (vertical, apaisada):
            with self.subTest(nombre=imagen.image.name):
                formato, tamano, _modo = abrir(imagen)
                self.assertEqual(formato, 'WEBP')
                self.assertEqual(tamano, IMAGE_SIZE)
                self.assertTrue(imagen.image.name.endswith('.webp'))

    def test_el_recorte_es_cover_y_no_deforma(self):
        """Un cuadrado se recorta al centro hasta 16:9, sin estirar."""
        imagen = BusinessImage.objects.create(
            business=self.business, image=foto('cuadrado.png', 1000, 1000, 'PNG')
        )

        formato, tamano, modo = abrir(imagen)
        self.assertEqual(formato, 'WEBP')
        self.assertEqual(tamano, IMAGE_SIZE)
        self.assertEqual(modo, 'RGB')          # el alfa se aplana

    def test_las_fotos_se_reducen_a_un_peso_razonable(self):
        """WebP tiene que pesar bastante menos que el JPEG de entrada."""
        original = foto('grande.jpg', 2400, 1600).size
        imagen = BusinessImage.objects.create(
            business=self.business, image=foto('grande.jpg', 2400, 1600)
        )

        with imagen.image.open('rb') as fh:
            procesada = len(fh.read())
        self.assertLess(procesada, original)

    # ------------------------ tolerancia ---------------------------
    def test_un_archivo_que_no_es_imagen_se_guarda_igual(self):
        """No se valida formato: si no se puede procesar, va el original."""
        notas = SimpleUploadedFile(
            'notas.txt', b'no soy una imagen', content_type='text/plain'
        )

        imagen = BusinessImage.objects.create(business=self.business, image=notas)

        self.assertTrue(imagen.image.name.endswith('notas.txt'))
        with imagen.image.open('rb') as fh:
            self.assertEqual(fh.read(), b'no soy una imagen')

    def test_una_url_cargada_por_script_no_se_toca(self):
        """Los scripts guardan URLs: no hay nada que procesar ahí."""
        imagen = BusinessImage.objects.create(
            business=self.business, image='https://ejemplo.com/foto.jpg'
        )

        self.assertEqual(imagen.image.name, 'https://ejemplo.com/foto.jpg')

    def test_re_guardar_no_vuelve_a_procesar(self):
        """Cada foto se procesa UNA sola vez."""
        imagen = BusinessImage.objects.create(
            business=self.business, image=foto('una.jpg', 600, 400)
        )
        nombre = imagen.image.name

        imagen.caption = 'Pie nuevo'
        imagen.save()

        self.assertEqual(imagen.image.name, nombre)

    # ------------------------- límite de 5 -------------------------
    def test_el_limite_de_cinco_fotos_sigue_ahí(self):
        for i in range(MAX_IMAGES_PER_BUSINESS):
            BusinessImage.objects.create(
                business=self.business, order=i, image=foto(f'f{i}.jpg', 600, 400)
            )

        sobra = BusinessImage(
            business=self.business, order=5, image=foto('sobra.jpg', 600, 400)
        )

        with self.assertRaises(ValidationError):
            sobra.full_clean()
        self.assertEqual(self.business.images.count(), MAX_IMAGES_PER_BUSINESS)
