"""Un lote de datos planos, cruzado contra la base (R5, §10-d).

Lo comparten dos comandos que por fuera no se parecen en nada:

* ``importar_municipio`` trae los candidatos de Overpass;
* ``cargar_fichas`` los trae de un JSON exportado de otra base.

Y por dentro tienen que hacer **exactamente** lo mismo: validar en la
puerta, cruzar ANTES de publicar y publicar solo el que cumpla el trio.
Si cada uno montara su propio bucle, el dia que alguien cambiara el orden
—crear primero y cruzar despues, por ejemplo— uno de los dos dejaria de
deduplicar y no se enteraria hasta ver dos fichas del mismo negocio a 400
km de distancia.

Este bucle vivia dentro del importador; sacarlo aqui es lo que permite
llevar datos de una base a otra sin que lo que llegue sea "casi" lo
mismo. Ninguno de los dos comandos importa al otro, solo a este modulo.
"""
from collections import Counter

from django.utils.text import slugify

from categories.models import Category

from . import geografia, ingreso, pendientes, validacion
from .models import Business


def categoria_de(datos):
    """La categoria del candidato, creandola si no existe.

    Aqui SI se crea: el nombre viene de OSM o de nuestra propia
    exportacion y es de fiar. El canal de envio, en cambio, solo busca la
    que ya hay, porque ahi el nombre lo teclea una persona y una errata no
    debe abrirle una categoria nueva al sistema.

    Sin nombre no hay categoria que crear: devuelve ``None``, que es lo
    que ``ingreso.crear`` entiende como "esta ficha no tiene categoria"
    (y por eso aparece como pendiente en el reporte de §11.1).
    """
    nombre = (datos.get('categoria') or '').strip()
    if not nombre:
        return None
    return Category.objects.get_or_create(
        name=nombre,
        defaults={'slug': slugify(nombre, allow_unicode=True)},
    )[0]


class Lote:
    """Un lote de candidatos, ya cruzado contra lo que ya existe en la base.

    Se usa asi::

        lote = Lote(radio=5, en_revision=en_revision, publicado=publicado)
        for datos in candidatos:
            lote.agregar(datos, cabecera)     # valida + cruza + crea
        entraron, publicados, esperan = lote.publicar()   # §10-f

    ``agregar`` no devuelve nada: lo que cambia queda en ``totales`` y
    ``rechazos``, que son los mismos contadores que imprimen los dos
    comandos. La lista de lo que hay que publicar se acumula hasta
    ``publicar()`` —publicar por ficha seria una consulta para cada
    candidato— y esa llamada la vacia, para que cada municipio se cierre
    el suyo y no se mezcle con el siguiente.
    """

    def __init__(self, *, radio, en_revision, publicado):
        self.radio = radio
        self.en_revision = en_revision
        self.publicado = publicado
        self.totales = Counter()
        self.rechazos = Counter()
        # Una sola carga: despues se va actualizando con lo que se crea,
        # en vez de consultar la base por cada candidato.
        self.indice = self._indice()
        self.tocados = []
        self.nuevos = []

    def _indice(self):
        """``{municipio: {nombre: negocio}}``, todo normalizado.

        Es el cruce de §10-d: con esto se sabe si un candidato ya existe
        sin tener que preguntarle a la base por cada uno.
        """
        indice = {}
        for biz in Business.objects.select_related('location').iterator():
            loc = getattr(biz, 'location', None)
            municipio = geografia.normalizar(
                loc.municipality if loc is not None else ''
            )
            nombre = geografia.normalizar(biz.name)
            if not nombre:
                continue
            indice.setdefault(municipio, {}).setdefault(nombre, biz)
        return indice

    def agregar(self, datos, cabecera):
        """Un candidato entero: lo rechaza, lo enriquece o lo crea."""
        clave_municipio = geografia.normalizar(cabecera['municipio'])
        lat, lng = datos.get('lat'), datos.get('lng')

        # La puerta, primero: lo mal formado ni siquiera llega a
        # comprobar de que municipio es (§11.5).
        motivos = validacion.validar(
            nombre=datos.get('nombre'),
            telefono=datos.get('telefono'),
            lat=lat,
            lng=lng,
            municipio=datos.get('municipio'),
            cabecera=cabecera,
            radio_km=self.radio,
        )
        if motivos:
            self.totales['rechazados'] += 1
            for motivo in motivos:
                self.rechazos[motivo] += 1
            return

        # Aqui si hace falta punto: sin el no hay por donde asignarle
        # municipio, y este camino trabaja por circulos. (La puerta de
        # §11.5 lo permite: ahi un dato sin punto va al reporte.)
        if lat is None or lng is None:
            self.totales['rechazados'] += 1
            self.rechazos['Sin punto: no hay coordenadas.'] += 1
            return

        # La cabecera mas cercana manda: con un radio amplio, lo que
        # queda mas cerca de otro municipio no es de este.
        destino = geografia.cabecera_mas_cercana(lat, lng, self.radio)
        if destino is None \
                or geografia.normalizar(destino['municipio']) != clave_municipio:
            # Le toca a otro municipio, que ya lo importara. No es un
            # error: con radios grandes los circulos se pisan.
            self.totales['le_toca_a_otro'] += 1
            return

        existente = validacion.duplicado(
            self.indice.get(clave_municipio, {}),
            datos.get('nombre'), lat, lng,
        )
        if existente is not None:
            self.totales['duplicados'] += 1
            # La categoria SI se crea aqui (el nombre viene de OSM y es de
            # fiar), pero solo si la ficha no tiene: es la misma condicion
            # con la que `enriquecer` la usaria.
            nueva = (
                categoria_de(datos)
                if not existente.category_id and datos.get('categoria')
                else None
            )
            if validacion.enriquecer(existente, datos, categoria=nueva):
                self.totales['enriquecidos'] += 1
                # Releer: `enriquecer` dejo en la instancia la cache de
                # "no tiene contacto" de antes de crearlo, y con ella
                # `cumple_trio` veria el telefono que acaba de ponerse.
                existente = Business.objects.get(pk=existente.pk)
                self.tocados.append(existente)
            return

        negocio = ingreso.crear(
            datos,
            categoria=categoria_de(datos),
            en_revision=self.en_revision,
            # La procedencia viaja con el dato. OSM no la trae (a_datos
            # no la pone), y ahi el default sigue siendo `importado`.
            procedencia=datos.get('procedencia') or 'importado',
        )
        self.nuevos.append(negocio)
        self.tocados.append(negocio)
        self.indice.setdefault(clave_municipio, {})[
            geografia.normalizar(negocio.name)] = negocio

    def publicar(self):
        """§10-f: publica lo de ESTE lote que cumpla el trio y lo vacia.

        Devuelve ``(entraron, publicados, esperan)``, los tres numeros de
        la linea de resumen por municipio. Se vacian las dos listas para
        que la siguiente llamada no vuelva a mirar lo ya publicado.
        """
        promovidos = pendientes.publicar_si_cumple(self.tocados, self.publicado)
        nuevos, self.nuevos = self.nuevos, []
        self.tocados = []

        publicados_nuevos = sum(
            1 for n in nuevos
            if n.publication_status_id == self.publicado.id
        )
        esperan = len(nuevos) - publicados_nuevos

        self.totales['creados'] += len(nuevos)
        self.totales['publicados'] += len(promovidos)
        self.totales['quedaron_en_revision'] += esperan
        return len(nuevos), len(promovidos), esperan
