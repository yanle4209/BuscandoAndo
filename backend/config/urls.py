from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static

# Admin personalizado (solo textos)
import config.admin  # noqa

# Vistas de importacion/exportacion (ANTES de admin.site.urls)
from import_views import get_import_view, get_export_view
from views import serve_react

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

# Serve React frontend in production
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^(?!api/|admin/|static/|media/).*(?:\.js|\.css|\.ico|\.png|\.jpg|\.svg|\.woff|\.woff2|\.map)$', serve_react),
        re_path(r'^(?!api/|admin/|static/|media/).*$', serve_react),
    ]
