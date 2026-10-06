"""Procesado de las fotos de negocio.

Regla única (la que pidió el usuario):

    tamaño fijo + recorte automático + formato ligero (WebP)

Se aplica a CADA foto nueva que entra por el admin o por cualquier
otro camino que acabe en ``BusinessImage.save()``. El único límite que
se valida sigue siendo ``MAX_IMAGES_PER_BUSINESS = 5``: aquí NO se
rechaza ningún archivo por formato ni por peso.

Si algo no se puede procesar (no es una imagen, está corrupto, Pillow
vino sin soporte WebP...), se devuelve el archivo ORIGINAL tal cual:
mejor una foto sin optimizar que una foto perdida.
"""

import io
import os

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

#: Tamaño fijo de TODAS las fotos: 16:9, la proporción que ya usan
#: la portada de la tarjeta (112 px de alto) y el carrusel del modal
#: (320 px). El recorte es centrado y "cover": se corta por el centro
#: lo que sobre, sin deformar.
IMAGE_SIZE = (1200, 675)

#: Calidad WebP: visible a simple vista, pero muy por debajo de un JPEG
#: de cámara. Método 6 = la compresión más lenta (y más pequeña).
WEBP_QUALITY = 75
WEBP_METHOD = 6


def process_image(uploaded):
    """Devuelve el archivo ya recortado al tamaño fijo y en WebP.

    ``uploaded`` es un archivo de Django (``UploadedFile``/``File``).
    Devuelve un ``ContentFile`` con nombre ``<original>.webp`` listo
    para subir, o el mismo archivo original si no se pudo procesar.

    En el fallo se hace ``seek(0)``: si no, el puntero quedaría al
    final del fichero y el storage subiría un archivo vacío.
    """
    if not uploaded:
        return uploaded

    try:
        with Image.open(uploaded) as im:
            im.load()                                   # falla si está roto
            im = ImageOps.exif_transpose(im)            # móvil -> vertical
            # Recorte centrado a la proporción objetivo (sin deformar).
            im = ImageOps.fit(
                im,
                IMAGE_SIZE,
                method=Image.LANCZOS,
                centering=(0.5, 0.5),
            )
            im = _a_rgb(im)

            buf = io.BytesIO()
            im.save(buf, format='WEBP', quality=WEBP_QUALITY, method=WEBP_METHOD)
    except Exception:
        # No es imagen / corrupto / sin WebP en este Pillow: el original.
        _volver_al_principio(uploaded)
        return uploaded

    nombre = os.path.splitext(os.path.basename(getattr(uploaded, 'name', '') or ''))[0]
    return ContentFile(buf.getvalue(), name=f'{nombre or "foto"}.webp')


def _a_rgb(im):
    """RGB puro para el encoder (WebP no admite paleta ni CMYK).

    El canal alfa se aplana sobre blanco: es lo que espera el carrusel
    y evita bordes fantasma sobre el velo marrón.
    """
    if im.mode in ('RGBA', 'LA', 'PA'):
        im = im.convert('RGBA')
        fondo = Image.new('RGB', im.size, (255, 255, 255))
        fondo.paste(im, mask=im.split()[-1])
        return fondo
    if im.mode != 'RGB':
        return im.convert('RGB')
    return im


def _volver_al_principio(uploaded):
    """Rebobina para que el storage no suba un fichero vacío."""
    try:
        if hasattr(uploaded, 'seek'):
            uploaded.seek(0)
    except Exception:                                   # pragma: no cover
        pass
