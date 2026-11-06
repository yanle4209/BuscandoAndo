"""Que le falta a cada ficha.

R5 publica sola una ficha cuando cumple los **obligatorios**
``nombre + direccion + telefono + imagen + punto``; todo lo demas
(categoria, horario, WhatsApp, correo, web, descripcion, estado) son
campos opcionales que se pueden rellenar mas adelante. La clave de este
modulo es que **nada de eso se guarda**: campo vacio = pendiente
(DISENO.md seccion 10, "Como se modela lo pendiente").

Sin esto, tres sitios tendrian que definir "que es estar incompleto" por su
cuenta: el importador que decide que se publica, el reporte de la seccion
11.1 que agrupa por campo faltante y el canal de envio de la 11.5 que
comprueba si lo que llega ya es publicable. Cada uno por su lado, el dia
que alguien cambie uno los otros dos seguirian creyendo lo anterior.

Solo calcula: no escribe en la base de datos.
"""

# El orden es el del reporte: los obligatorios primero porque es lo que
# separa "se publica sola" de "hay que editarla a mano", el resto despues
# porque es lo que un editor va completando.
CAMPOS = [
    ('nombre', 'Nombre'),
    ('direccion', 'Dirección'),
    ('telefono', 'Teléfono'),
    ('imagen', 'Imagen'),
    ('punto', 'Punto (coordenadas)'),
    ('categoria', 'Categoría'),
    ('horario', 'Horario'),
    ('whatsapp', 'WhatsApp'),
    ('correo', 'Correo'),
    ('web', 'Sitio web'),
    ('descripcion', 'Descripción'),
    ('estado', 'Estado operativo'),
]

# Lo que exige la publicacion automatica (§10-f, y luego lo decidido para
# el reporte): los cinco requeridos —nombre, direccion, telefono, imagen
# y punto— tienen que estar antes de publicar; el resto es opcional.
OBLIGATORIOS = ('nombre', 'direccion', 'telefono', 'imagen', 'punto')

ETIQUETAS = dict(CAMPOS)


def _limpio(valor):
    """Un valor cuenta si no es ``None`` ni esta vacio (o en blanco)."""
    return bool(valor and str(valor).strip())


def faltantes_de(biz):
    """Las claves de ``CAMPOS`` que ``biz`` todavia no tiene.

    Recorre el objeto entero, no solo los obligatorios: un negocio
    publicado sin horario tambien es un pendiente para quien edita el
    municipio.

    Espera ``location`` y ``contact`` ya traidos (``select_related``) y
    ``hours`` e ``images`` precargados (``prefetch_related``); si no lo
    estan, cada ficha cuesta una consulta.
    """
    faltan = []

    if not _limpio(biz.name):
        faltan.append('nombre')

    loc = getattr(biz, 'location', None)
    if loc is None:
        # Sin fila de ubicacion no hay punto NI direccion: son el mismo
        # hueco visto dos veces, y el reporte debe contar los dos.
        faltan.append('punto')
        faltan.append('direccion')
    else:
        if loc.latitude is None or loc.longitude is None:
            faltan.append('punto')
        if not _limpio(loc.street):
            faltan.append('direccion')

    # Sin foto no se publica: la imagen es obligatoria, y una ficha que
    # se quedo sin ella vuelve al reporte aunque este publicada.
    if not biz.images.all():
        faltan.append('imagen')

    contact = getattr(biz, 'contact', None)
    if contact is None:
        faltan.extend(['telefono', 'whatsapp', 'correo', 'web'])
    else:
        if not _limpio(contact.phone):
            faltan.append('telefono')
        if not _limpio(contact.whatsapp):
            faltan.append('whatsapp')
        if not _limpio(contact.email):
            faltan.append('correo')
        if not _limpio(contact.website):
            faltan.append('web')

    if biz.category_id is None:
        faltan.append('categoria')
    if not _limpio(biz.description):
        faltan.append('descripcion')
    if biz.operational_status_id is None:
        faltan.append('estado')

    # Un dia cerrado no es horario: hace falta al menos una franja abierta.
    if not any(
        h.open_time and h.close_time and not h.is_closed
        for h in biz.hours.all()
    ):
        faltan.append('horario')

    return faltan


def cumple_obligatorios(biz):
    """R5: se puede publicar sola si y solo si no le falta nada obligatorio.

    Se define como el complemento de ``faltantes_de`` en vez de comprobar
    los cinco campos por su cuenta: asi no puede haber dos versiones de
    los obligatorios que acaben divergiendo.
    """
    faltan = faltantes_de(biz)
    return not any(campo in faltan for campo in OBLIGATORIOS)


def particionar(negocios):
    """Los tres cubos del reporte de §11.1, en una sola pasada.

    * ``revision`` — le falta ALGO obligatorio, o todavia no se ha
      publicado: es lo que hay que completar o publicar a mano. Aunque
      este publicada, si le falta un requerido VUELVE a esta lista (lo
      pidio el editor: procurar que los negocios tengan todo lo
      requerido antes de publicar).
    * ``publicadas`` — ya esta publicada con TODOS los obligatorios y
      aun le faltan opcionales: sale en la lista aparte «publicadas con
      faltantes», para rellenarlas mas adelante.
    * ``completas`` — publicada y sin ningun campo faltante.

    Cubos disjuntos: cada ficha cae exactamente en uno. Devuelve
    ``{cubo: [(ficha, faltan), ...]}``; ``faltan`` viene de la misma
    lectura que decide el cubo, para que el contador de la fila y la
    lista digan lo mismo.
    """
    cubos = {'revision': [], 'publicadas': [], 'completas': []}
    for biz in negocios:
        faltan = faltantes_de(biz)
        publicada = biz.publication_status.slug == 'publicado'
        if not publicada or any(campo in faltan for campo in OBLIGATORIOS):
            cubos['revision'].append((biz, faltan))
        elif faltan:
            cubos['publicadas'].append((biz, faltan))
        else:
            cubos['completas'].append((biz, faltan))
    return cubos


def contar_pendientes(negocios):
    """Agrupa ``negocios`` por campo faltante, para el reporte de §11.1.

    Orden de trabajo: **los obligatorios primero** — es lo que separa una
    ficha publicable sola de una que hay que completar a mano — y dentro
    de cada grupo, de mas a menos frecuente. Sin el primer criterio, los
    campos que no tiene casi nadie (WhatsApp, web) taparian el telefono,
    que es el que decide si algo se publica.
    """
    conteo = {clave: 0 for clave, _ in CAMPOS}
    for biz in negocios:
        for campo in faltantes_de(biz):
            conteo[campo] += 1

    filas = [
        {'campo': campo, 'etiqueta': ETIQUETAS[campo],
         'en_obligatorio': campo in OBLIGATORIOS, 'cantidad': conteo[campo]}
        for campo, _ in CAMPOS
        if conteo[campo]
    ]
    filas.sort(key=lambda fila: (0 if fila['en_obligatorio'] else 1,
                                 -fila['cantidad'], fila['campo']))
    return filas


def publicar_si_cumple(negocios, estado_publicado):
    """§10-f: de lo que acaba de entrar, se publica el que cumpla los
    obligatorios.

    Devuelve las promovidas. Vive aqui y no en el importador ni en el
    endpoint porque es la MISMA regla para los dos: R5 no distingue entre
    lo que viene de OSM y lo que manda un colaborador.

    Solo ``procedencia='importado'`` o ``'levantado'``: una ficha creada a
    mano se queda en revision aunque cumpla los obligatorios, que es
    quien la publica (VISION.md). Si esto se abriera a 'manual', el
    importador publicaria por su cuenta fichas que alguien dejo a
    proposito sin publicar.
    """
    promovidas = []
    for biz in negocios:
        if biz.publication_status_id == estado_publicado.id:
            continue
        if biz.procedencia not in ('importado', 'levantado'):
            continue
        if not cumple_obligatorios(biz):
            continue
        biz.publication_status = estado_publicado
        biz.save(update_fields=['publication_status', 'updated_at'])
        promovidas.append(biz)
    return promovidas
