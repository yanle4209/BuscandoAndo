"""
View to serve the React SPA frontend in production.
Uses mimetypes to set correct Content-Type for static assets.

Ademas de servir el build, esta capa es la encargada del SEO on-page
(auditoria C): el titulo, la description, Open Graph y el canonical se
pintan AQUI, en el servidor, con los datos reales de la ficha. Sin
react-helmet y sin esperar a que arranque el JS — que es justo lo que
Google y WhatsApp leen.
"""
import html
import mimetypes
import re
import urllib.parse

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

# ---------------------------------------------------------------------------
# Rutas del SPA (frontend/src/App.jsx): SOLO estas devuelven index.html.
# Cualquier otra peticion es un 404 de verdad: el "200 para todo" era un
# soft-404 que Google podia indexar como pagina vacia (auditoria C, nº 3).
# ---------------------------------------------------------------------------
RUTAS_SPA = frozenset({'', 'index.html', 'levantamiento'})
RUTA_NEGOCIO = re.compile(r'^business/(?P<slug>[^/]+)/?$')


def _sitio():
    """La URL publica del sitio, sin barra final."""
    return settings.SITIO_URL.rstrip('/')


def _escapar(texto):
    """Texto seguro para atributo de meta (comillas y angles incluidos)."""
    return html.escape((texto or '').strip(), quote=True)


def _recortar(texto, maximo=160):
    """Description para meta: una linea, sin cortar a media palabra."""
    texto = ' '.join((texto or '').split())
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo - 1]
    if ' ' in corte:
        corte = corte.rsplit(' ', 1)[0]
    return corte + '…'


def _metas_ficha(slug):
    """Metas de ``/business/<slug>/``.

    Devuelve ``None`` si la ficha no existe o no esta publicada (-> 404,
    misma regla que el ``retrieve`` de la API) y un dict con las metas en
    caso contrario. Las fichas fuera de fase vuelven con ``noindex``: el
    enlace directo sigue abriendo (DISENO.md 13) pero Google no las
    indexa por su cuenta.
    """
    from businesses import geografia
    from businesses.models import Business

    ficha = (
        Business.objects
        .filter(slug=slug, publication_status__slug='publicado')
        .select_related('category', 'location')
        .prefetch_related('images')
        .first()
    )
    if ficha is None:
        return None

    # `location` es una OneToOne inversa: una ficha SIN fila de
    # ubicacion lanza DoesNotExist al acceder (y ese error hereda de
    # AttributeError, por eso el getattr con default y no un try).
    # El enlace directo tiene que seguir abriendo igualmente.
    loc = getattr(ficha, 'location', None)
    municipio = loc.municipality if loc else ''
    provincia = loc.province if loc else ''
    categoria = ficha.category.name if ficha.category else ''

    lugar = ', '.join(p for p in (municipio, provincia) if p)
    if lugar and categoria:
        titulo = '%s – %s en %s | BuscandoAndo' % (ficha.name, categoria,
                                                   lugar)
    elif lugar:
        titulo = '%s en %s | BuscandoAndo' % (ficha.name, lugar)
    else:
        titulo = '%s | BuscandoAndo' % ficha.name

    descripcion = _recortar(ficha.short_description or ficha.description)

    # Primera foto de la ficha para la preview de WhatsApp; si no tiene
    # (o el storage no esta configurado, que pasa en local), la tarjeta
    # generica del sitio. OJO: `foto.image` es un ImageFieldFile — hay
    # que pedir `.url`, que es el que Cloudinary expande a la URL
    # absoluta. Un fallo aqui jamas debe tumbar la pagina: es una meta.
    imagen = None
    for foto in ficha.images.all():
        try:
            imagen = foto.image.url
        except Exception:
            imagen = None
        break
    if not imagen:
        imagen = _sitio() + '/og.png'
    elif imagen.startswith('/'):
        imagen = _sitio() + imagen

    return {
        'titulo': titulo,
        'descripcion': descripcion,
        'imagen': imagen,
        'url': '%s/business/%s' % (_sitio(), ficha.slug),
        # Sin ubicacion no se ensena en el listado, asi que tampoco se
        # anuncia (la misma regla que la fase).
        'noindex': not geografia.en_fase(provincia),
    }


def _metas_para_ruta(rel):
    """Metas de la ruta ``rel`` (relativa al build); ``None`` -> 404."""
    match = RUTA_NEGOCIO.match(rel)
    if match:
        return _metas_ficha(match.group('slug'))

    # Personalizado a mano desde el panel (DISENO 15): las rutas fijas
    # se configuran en la base de datos, sin tocar codigo y sin
    # desplegar — el sitio es dinamico y lo de hoy no es lo de manana.
    # Sin fila para esta clave (o si la base no contesta) mandan los
    # valores de siempre de mas abajo: un fallo aqui jamas debe tumbar
    # la pagina.
    clave = '' if rel == 'index.html' else rel
    if clave in RUTAS_SPA:
        try:
            from seo.models import SeoRuta
            personalizado = SeoRuta.objects.filter(ruta=clave).first()
        except Exception:
            personalizado = None
        if personalizado:
            imagen = personalizado.imagen or '/og.png'
            if imagen.startswith('/'):
                imagen = _sitio() + imagen
            return {
                'titulo': personalizado.titulo,
                'descripcion': personalizado.descripcion,
                'imagen': imagen,
                'url': _sitio() + ('/' if not clave else '/' + clave),
                'noindex': personalizado.noindex,
            }

    if rel == 'levantamiento':
        # Herramienta de campo sin enlace publico (DISENO.md 11.5):
        # se sirve para quien teclea la ruta, pero no se indexa.
        return {
            'titulo': 'Levantamiento de fichas | BuscandoAndo',
            'descripcion': ('Herramienta de captura de fichas de '
                            'BuscandoAndo para colaboradores de campo.'),
            'imagen': _sitio() + '/og.png',
            'url': _sitio() + '/levantamiento',
            'noindex': True,
        }

    if rel in RUTAS_SPA:
        return {
            'titulo': 'BuscandoAndo - Encuentra negocios en República '
                      'Dominicana',
            'descripcion': ('Directorio de negocios de República '
                            'Dominicana: encuentra restaurantes, farmacias, '
                            'talleres y más negocios cerca de ti con fotos, '
                            'horarios, teléfono y ubicación.'),
            'imagen': _sitio() + '/og.png',
            'url': _sitio() + '/',
            'noindex': False,
        }

    return None


def _inyectar_metas(index, metas):
    """Sustituye el titulo del index y añade las metas antes de </head>."""
    robots = 'noindex,nofollow' if metas['noindex'] else 'index,follow'
    bloque = '\n    '.join([
        '<meta name="description" content="%s" />'
        % _escapar(metas['descripcion']),
        '<meta name="robots" content="%s" />' % robots,
        '<link rel="canonical" href="%s" />' % _escapar(metas['url']),
        '<meta property="og:type" content="website" />',
        '<meta property="og:site_name" content="BuscandoAndo" />',
        '<meta property="og:locale" content="es_DO" />',
        '<meta property="og:title" content="%s" />'
        % _escapar(metas['titulo']),
        '<meta property="og:description" content="%s" />'
        % _escapar(metas['descripcion']),
        '<meta property="og:url" content="%s" />' % _escapar(metas['url']),
        '<meta property="og:image" content="%s" />'
        % _escapar(metas['imagen']),
        '<meta name="twitter:card" content="summary_large_image" />',
        '<meta name="twitter:title" content="%s" />'
        % _escapar(metas['titulo']),
        '<meta name="twitter:description" content="%s" />'
        % _escapar(metas['descripcion']),
        '<meta name="twitter:image" content="%s" />'
        % _escapar(metas['imagen']),
    ])
    index = re.sub(r'<title>.*?</title>',
                   '<title>%s</title>' % _escapar(metas['titulo']),
                   index, count=1, flags=re.S)
    return index.replace('</head>', bloque + '\n  </head>', 1)


def serve_react(request, path=''):
    """Serve React build files or index.html for SPA routing."""
    build_dir = settings.REACT_BUILD_DIR

    # Extract path from request if not provided by URL pattern
    if not path:
        path = request.path_info.lstrip('/')

    # If requesting a specific file (JS, CSS, images, etc.)
    if path:
        # SEGURIDAD (auditoria del 19/oct): `path` viene de la URL, y
        # pathlib une segmentos absolutos REEMPLAZANDO la base — con
        # "//etc/passwd" esta vista abria /etc/passwd del servidor
        # (lectura arbitraria de ficheros; se llegaba a leer el
        # render.yaml entero del repositorio desplegado). Dos barreras:
        # la ruta se aplana a relativa, y ademas se exige que resuelva
        # DENTRO del build. Lo que no este dentro no se sirve: cae al
        # index del SPA, que es lo que ya pasaba con las rutas normales.
        base = build_dir.resolve()
        file_path = (build_dir / path.lstrip('/')).resolve()
        if file_path.is_relative_to(base) and file_path.is_file():
            content_type, _ = mimetypes.guess_type(str(file_path))
            # .webmanifest no esta en la tabla de mimetypes de todos los
            # sistemas (Windows no lo trae; en Linux depende de la
            # version). Con el tipo equivocado el navegador no acepta el
            # manifest (auditoria E), asi que se declara a mano.
            if file_path.suffix == '.webmanifest':
                content_type = 'application/manifest+json'
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            # Asset con hash en el nombre (index-97q9MQp8.js): el nombre
            # cambia en cada build, asi que se puede conservar para
            # siempre. Sin esto el navegador releia los bundles en cada
            # visita.
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
            return response

    # SOLO las rutas conocidas del SPA caen en el index (auditoria C:
    # el 200 universal era un soft-404). `None` incluye ademas las
    # fichas no publicadas o inexistentes: mismas 404 que la API.
    rel = path.lstrip('/')
    metas = _metas_para_ruta(rel)
    if metas is None:
        raise Http404('Ruta desconocida: %s' % rel)

    index_path = build_dir / 'index.html'
    if index_path.exists():
        # El index se lee como texto para poder inyectar las metas de la
        # ruta: es un fichero de 0,6 kB y solo se toca cuando piden HTML
        # (los assets de arriba no pasan por aqui).
        index = index_path.read_text(encoding='utf-8')
        response = HttpResponse(_inyectar_metas(index, metas),
                                content_type='text/html; charset=utf-8')
        # El index.html es el que decide que bundle se carga, y sin
        # Cache-Control el navegador aplicaba cache heuristica: se
        # quedaba con el HTML viejo y con el JS viejo, y los deploys no
        # se reflejaban hasta un Ctrl+Shift+R manual. "no-cache" obliga
        # a revalidar en cada visita (el fichero pesa 0,6 kB).
        response['Cache-Control'] = 'no-cache'
        return response

    raise Http404('Frontend not built. Run: cd frontend && npm run build')


def sitemap_xml(request):
    """``/sitemap.xml``: las fichas publicadas DENTRO de la fase.

    Auditoria C: robots.txt y sitemap devolvian el HTML de la SPA, asi
    que Google no podia leer ni las reglas ni el inventario. Aqui se
    genera desde la misma base y con el MISMO filtro que el listado
    (``geografia.q_fase``), asi que lo que esta fuera de fase no se
    anuncia — esas fichas siguen abriendose por enlace directo pero con
    noindex (ver ``serve_react``).

    740 <loc> de fase actualmente: un unico fichero, muy por debajo del
    limite de 50.000 que admite el formato.
    """
    from businesses import geografia
    from businesses.models import Business

    sitio = _sitio()
    filas = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <url>',
        '    <loc>%s/</loc>' % sitio,
        '    <changefreq>daily</changefreq>',
        '    <priority>1.0</priority>',
        '  </url>',
    ]

    fichas = (
        Business.objects
        .filter(geografia.q_fase(), publication_status__slug='publicado')
        .order_by('-created_at')
        .values_list('slug', 'created_at')
    )
    for slug, creado in fichas:
        # quote: los slugs de la base pueden llevar acentos
        # (estadio-josé-maría-hidalgo-san) y <loc> exige la URL escapada.
        loc = urllib.parse.quote('%s/business/%s' % (sitio, slug),
                                 safe=':/')
        filas += [
            '  <url>',
            '    <loc>%s</loc>' % loc,
            '    <lastmod>%s</lastmod>' % creado.date().isoformat(),
            '    <changefreq>weekly</changefreq>',
            '    <priority>0.7</priority>',
            '  </url>',
        ]
    filas.append('</urlset>')

    respuesta = HttpResponse('\n'.join(filas) + '\n',
                             content_type='application/xml; charset=utf-8')
    # Solo cambia cuando entran fichas nuevas: una hora de vida sirve
    # y evita regenerar 740 filas en cada rastreo.
    respuesta['Cache-Control'] = 'public, max-age=3600'
    return respuesta


def _robots_efectivo():
    """El texto del robots.txt que se sirve hoy.

    Manda la fila editable del panel (DISENO 15); si no la hay — o esta
    en blanco —, manda el fichero del build, que es el comportamiento
    de siempre. La base solo ANYADE control, nunca lo quita.
    """
    try:
        from seo.models import SeoRobots
        fila = SeoRobots.cargar()
        if fila and fila.contenido.strip():
            return fila.contenido
    except Exception:
        pass
    try:
        return (settings.REACT_BUILD_DIR / 'robots.txt').read_text(
            encoding='utf-8')
    except OSError:
        return None


def robots_txt(request):
    """``/robots.txt`` editable desde el panel (DISENO 15).

    Antes lo servia el tramoya de ficheros de ``serve_react``; ahora la
    ruta tiene vista propia para que el panel pueda cambiarlo sin
    desplegar. text/plain (auditoria C) y no-cache: pesa muy poco y un
    cambio debe notarse en el primer rastreo.
    """
    contenido = _robots_efectivo() or 'User-agent: *\nAllow: /\n'
    respuesta = HttpResponse(contenido,
                             content_type='text/plain; charset=utf-8')
    respuesta['Cache-Control'] = 'no-cache'
    return respuesta


def admin_seo(request):
    """Panel SEO del admin (DISENO 15): el estado REAL, leido del sitio.

    La tabla de metas se lee desde las MISMAS vistas que las sirven al
    publico (``_metas_para_ruta``), asi que aqui no puede haber una
    copia desfasada; guardar lo que se cambia a mano va por el modelo
    registrado (metas por ruta y robots.txt). Entra por ``admin.site.admin_view``
    (solo staff, sin cache) y reutiliza la plantilla base del admin:
    misma cabecera, mismo menu y mismo estilo que el resto del panel.
    """
    from django.contrib.admin import site as admin_site
    from django.shortcuts import render

    from businesses import geografia
    from businesses.models import Business

    # La ficha de ejemplo es la mas reciente PUBLICADA y en fase: es
    # tal cual como la ve un buscador que entra por el sitemap.
    de_fase = (
        Business.objects
        .filter(geografia.q_fase(), publication_status__slug='publicado')
        .order_by('-created_at')
    )
    slug_ejemplo = de_fase.values_list('slug', flat=True).first()

    # Las metas configuradas a mano, con su clave: cada fila del panel
    # lleva su enlace de edicion si esta guardada en la base.
    from seo.models import SeoRuta
    editables = {fila.ruta: fila.pk for fila in SeoRuta.objects.all()}

    filas = [
        {'ruta': '/', 'editar_pk': editables.get(''),
         'metas': _metas_para_ruta('')},
        {'ruta': '/levantamiento',
         'editar_pk': editables.get('levantamiento'),
         'metas': _metas_para_ruta('levantamiento')},
    ]
    if slug_ejemplo:
        filas.insert(1, {
            'ruta': '/business/%s' % slug_ejemplo,
            'editar_pk': None,
            'metas': _metas_para_ruta('business/%s' % slug_ejemplo),
        })

    # robots.txt: la configuracion editable del panel (fila de la base)
    # con el fichero del build como respaldo.
    robots = _robots_efectivo()

    contexto = admin_site.each_context(request)
    contexto.update({
        'title': 'SEO',
        'filas': filas,
        'robots_lineas': (
            [linea for linea in robots.splitlines()
             if linea.strip() and not linea.startswith('#')]
            if robots else None
        ),
        'fichas_sitemap': de_fase.count(),
        'fichas_publicadas': Business.objects.filter(
            publication_status__slug='publicado').count(),
        'provincias_fase': settings.FASE1_PROVINCIAS,
    })
    return render(request, 'admin/seo_panel.html', contexto)
