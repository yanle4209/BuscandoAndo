from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404
import os

# Admin personalizado (solo textos)
import config.admin  # noqa

# Vistas de importacion/exportacion (ANTES de admin.site.urls)
from import_views import get_import_view, get_export_view
from views import serve_react


def serve_media(request, path):
    """Sirve archivos de MEDIA_ROOT en produccion."""
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.isfile(file_path):
        response = FileResponse(open(file_path, 'rb'))
        # Cache headers para evitar re-descargar
        response['Cache-Control'] = 'public, max-age=86400'
        return response
    raise Http404


urlpatterns = [
    path('admin/import-json/', get_import_view(), name='import_json'),
    path('admin/export-json/', get_export_view(), name='export_json'),
    path('admin/', admin.site.urls),
    path('api/', include('businesses.urls')),
    path('api/', include('categories.urls')),
]

# Media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # En produccion, servir media files con vista custom
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media, name='serve_media'),
    ]

# Serve React frontend in production
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^(?!api/|admin/|static/|media/)(?P<path>.*)$', serve_react),
    ]
