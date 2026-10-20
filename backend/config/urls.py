from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings

# Admin personalizado (solo textos)
import config.admin  # noqa

# Health check de Render (ver config/health.py)
from config.health import health

# Vistas de importacion/exportacion (ANTES de admin.site.urls)
from import_views import get_import_view, get_export_view
from views import serve_react, sitemap_xml

urlpatterns = [
    # Health check de Render. Va PRIMERO: es la ruta que Render vigila
    # cada pocos segundos (render.yaml -> healthCheckPath).
    path('api/health/', health, name='health'),

    path('admin/import-json/', get_import_view(), name='import_json'),
    path('admin/export-json/', get_export_view(), name='export_json'),
    path('admin/', admin.site.urls),
    path('api/', include('businesses.urls')),
    path('api/', include('categories.urls')),

    # Auditoria C: el sitemap era el HTML de la SPA (200 con
    # content-type text/html). Se genera aqui desde la base, ya filtrado
    # a las fichas de fase, y ANTES del fallback de React para que no lo
    # tape.
    path('sitemap.xml', sitemap_xml, name='sitemap'),
]

# Media files served by Cloudinary (no local serving needed)

# Serve React frontend in production
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^(?!api/|admin/|static/|media/)(?P<path>.*)$', serve_react),
    ]
