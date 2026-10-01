"""Que le falta a cada ficha.

R5 publica sola una ficha cuando cumple el trio ``nombre + telefono +
punto``; todo lo demas (horario, WhatsApp, correo, direccion, categoria,
web, descripcion, estado) son campos pendientes. La clave de este modulo es
que **nada de eso se guarda**: campo vacio = pendiente (DISENO.md seccion
10, "Como se modela lo pendiente").

Sin esto, tres sitios tendrian que definir "que es estar incompleto" por su
cuenta: el importador que decide que se publica, el reporte de la seccion
11.1 que agrupa por campo faltante y el canal de envio de la 11.5 que
comprueba si lo que llega ya es publicable. Cada uno por su lado, el dia
que alguien cambie uno los otros dos seguirian creyendo lo anterior.

Solo calcula: no escribe en la base de datos.
"""

# El orden es el del reporte: el trio primero porque es lo que separa
# "se publica sola" de "hay que editarla a mano", el resto despues porque
# es lo que un editor va completando.
CAMPOS = [
    ('nombre', 'Nombre'),
    ('telefono', 'Telefono'),
    ('punto', 'Punto (coordenadas)'),
    ('categoria', 'Categoria'),
    ('direccion', 'Direccion'),
    ('horario', 'Horario'),
    ('whatsapp', 'WhatsApp'),
    ('correo', 'Correo'),
    ('web', 'Sitio web'),
    ('descripcion', 'Descripcion'),
    ('estado', 'Estado operativo'),
]

# Lo que exige la publicacion automatica (§10-f: el telefono es obligatorio
# porque es el propio trio, no un extra).
TRIO = ('nombre', 'telefono', 'punto')

ETIQUETAS = dict(CAMPOS)


def _limpio(valor):
    """Un valor cuenta si no es ``None`` ni esta vacio (o en blanco)."""
    return bool(valor and str(valor).strip())


def faltantes_de(biz):
    """Las claves de ``CAMPOS`` que ``biz`` todavia no tiene.

    Recorre el objeto entero, no solo el trio: un negocio publicado sin
    horario tambien es un pendiente para quien edita el municipio.

    Espera ``location`` y ``contact`` ya traidos (``select_related``) y
    ``hours`` precargado (``prefetch_related``); si no lo estan, cada
    ficha cuesta una consulta.
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


def cumple_trio(biz):
    """R5: se puede publicar sola si y solo si no le falta nada del trio.

    Se define como el complemento de ``faltantes_de`` en vez de comprobar
    los tres campos por su cuenta: asi no puede haber dos versiones del
    trio que acaben divergiendo.
    """
    faltan = faltantes_de(biz)
    return not any(campo in faltan for campo in TRIO)


def contar_pendientes(negocios):
    """Agrupa ``negocios`` por campo faltante, para el reporte de §11.1.

    Orden de trabajo: **el trio primero** — es lo que separa una ficha
    publicable sola de una que hay que completar a mano — y dentro de cada
    grupo, de mas a menos frecuente. Sin el primer criterio, los campos que
    no tiene casi nadie (WhatsApp, web) taparian el telefono, que es el
    que decide si algo se publica.
    """
    conteo = {clave: 0 for clave, _ in CAMPOS}
    for biz in negocios:
        for campo in faltantes_de(biz):
            conteo[campo] += 1

    filas = [
        {'campo': campo, 'etiqueta': ETIQUETAS[campo],
         'en_trio': campo in TRIO, 'cantidad': conteo[campo]}
        for campo, _ in CAMPOS
        if conteo[campo]
    ]
    filas.sort(key=lambda fila: (0 if fila['en_trio'] else 1,
                                 -fila['cantidad'], fila['campo']))
    return filas


def publicar_si_cumple(negocios, estado_publicado):
    """§10-f: de lo que acaba de entrar, se publica el que cumpla el trio.

    Devuelve las promovidas. Vive aqui y no en el importador ni en el
    endpoint porque es la MISMA regla para los dos: R5 no distingue entre
    lo que viene de OSM y lo que manda un colaborador.

    Solo ``procedencia='importado'`` o ``'levantado'``: una ficha creada a
    mano se queda en revision aunque cumpla el trio, que es quien la
    publica (VISION.md). Si esto se abriera a 'manual', el importador
    publicaria por su cuenta fichas que alguien dejo a proposito sin
    publicar.
    """
    promovidas = []
    for biz in negocios:
        if biz.publication_status_id == estado_publicado.id:
            continue
        if biz.procedencia not in ('importado', 'levantado'):
            continue
        if not cumple_trio(biz):
            continue
        biz.publication_status = estado_publicado
        biz.save(update_fields=['publication_status', 'updated_at'])
        promovidas.append(biz)
    return promovidas
