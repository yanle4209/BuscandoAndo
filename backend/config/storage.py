# -*- coding: utf-8 -*-
"""Storage de media que le dice a Cloudinary el tipo real de cada archivo.

``MediaCloudinaryStorage`` sube TODO con ``resource_type='image'``
(``RESOURCE_TYPE`` fijo en la clase): la API de Cloudinary rechaza un
MP4 con 400 *Invalid image file* — el Server Error (500) al guardar un
anuncio de video en el panel de produccion el 15/nov/2026. Cloudinary
no infiere el tipo del archivo: hay que pasarselo (docs oficiales:
«resource_type => image is required; a video uploaded without this
option fails»).

En local nunca se ve este fallo: sin credenciales de Cloudinary,
settings.py cae a ``FileSystemStorage`` y el archivo va a disco.

El metodo que hay que sobreescribir es ``_get_resource_type(name)`` y
lo usan los tres caminos del storage: la subida (``_save`` →
``_upload``), la URL (``_get_url``) y el borrado (``delete``), asi que
con una sola pieza quedan correctos: ``.../video/upload/...`` para video
(si no, el ``<video>`` de la celda pediria ``.../image/upload/...`` y
Cloudinary devolveria 404) y ``.../image/upload/...`` para el resto.
"""

from cloudinary_storage.storage import (
    RESOURCE_TYPES,
    MediaCloudinaryStorage,
)

#: Extensiones que Cloudinary solo acepta como video. Tiene que cuadrar
#: con las que ``Business.clean()`` deja subir en ``ad_video``.
VIDEO_EXTS = {'mp4', 'm4v', 'webm', 'mov'}


class MediaStorage(MediaCloudinaryStorage):
    """Cloudinary por tipo de archivo: video donde hay video."""

    def _get_resource_type(self, name):
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if ext in VIDEO_EXTS:
            return RESOURCE_TYPES['VIDEO']
        return super()._get_resource_type(name)
