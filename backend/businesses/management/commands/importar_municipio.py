"""Importa los negocios de un municipio desde OpenStreetMap (R5).

    python manage.py importar_municipio Moca
    python manage.py importar_municipio --todos
    python manage.py importar_municipio Moca --radio 12

En este orden, y por este orden porque el paso 3 obliga §10-d:

1. trae los candidatos del circulo de la cabecera (los reparte por la
   cabecera **mas cercana**, para que con radios grandes no se cuele
   nadie en un municipio que no le toca);
2. **valida en la puerta** — lo mal formado se descarta con su motivo y
   no llega a estar pendiente de nada (§11.5);
3. **cruza contra lo que ya existe** — si es un duplicado, se le rellena
   lo que le falta a la ficha que ya esta; nunca se crea una segunda
   (§10-d: OSM trae telefonos que en muchos casos nosotros no tenemos);
4. crea el resto como `en-revision` con `procedencia='importado'`;
5. y de lo que acaba de crear, **publica el que cumpla el trio** (§10-f:
   nombre + telefono + punto). Lo que no lo cumple **no se descarta**:
   se queda en `en-revision` y sale en el reporte de §11.1.

Las fichas creadas a mano (`procedencia='manual'`) nunca se publican solas
ni siquiera si cumplen el trio: eso sigue siendo el admin (VISION.md).
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from categories.models import Category
from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from businesses import geografia, ingreso, osm, pendientes, validacion
from businesses.models import Business


class Command(BaseCommand):
    help = ('Importa los negocios de un municipio (o de todos) desde '
            'OpenStreetMap, validando y deduplicando antes de publicar.')

    def add_arguments(self, parser):
        parser.add_argument(
            'municipio', nargs='?',
            help='Municipio del padron de cabeceras. Innecesario con --todos.',
        )
        parser.add_argument(
            '--todos', action='store_true',
            help='Importa los 158 municipios del padron.',
        )
        parser.add_argument(
            '--radio', type=float, default=geografia.RADIO_KM,
            help='Radio de la consulta y del corte por cabecera, en km '
                 '(por defecto %g, el de R1).' % geografia.RADIO_KM,
        )

    def handle(self, *args, **opciones):
        radio = opciones['radio']
        if radio <= 0:
            raise CommandError('--radio tiene que ser un numero positivo.')

        if opciones['todos']:
            objetivos = [cab['municipio'] for cab in geografia.cabeceras()]
        elif opciones['municipio']:
            objetivos = [opciones['municipio']]
        else:
            raise CommandError('Dime un municipio, o usa --todos.')

        # Sin estos cuatro no hay donde poner lo que entre. Se comprueba
        # aqui y no a mitad de la importacion: una ficha sin estado
        # operativo se veria "Cerrado" en el frontend, que es mentira.
        self.publicado = PublicationStatus.objects.get(slug='publicado')
        self.en_revision = PublicationStatus.objects.get(slug='en-revision')
        for slug in ('abierto', 'cerrado'):
            if not OperationalStatus.objects.filter(slug=slug).exists():
                raise CommandError(
                    'Falta el estado operativo "%s": cargalo antes de '
                    'importar.' % slug
                )

        # Una sola carga: despues se va actualizando con lo que se crea,
        # en vez de consultar la base por cada candidato.
        indice = self._indice_por_municipio()

        totales = Counter()
        rechazos = Counter()

        for numero, municipio in enumerate(objetivos, 1):
            self.stdout.write('[%d/%d] %s'
                              % (numero, len(objetivos), municipio))
            self._importar(municipio, radio, indice, totales, rechazos)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('RESULTADO'))
        for clave in ('creados', 'publicados', 'quedaron_en_revision',
                      'duplicados', 'enriquecidos', 'rechazados',
                      'le_toca_a_otro', 'sin_datos', 'sin_cabecera'):
            self.stdout.write('  %-22s %d' % (clave, totales[clave]))
        if rechazos:
            self.stdout.write('  motivos:')
            for motivo, cantidad in rechazos.most_common():
                self.stdout.write('    %d  %s' % (cantidad, motivo))

    # ------------------------------------------------------------------
    def _indice_por_municipio(self):
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

    def _importar(self, municipio, radio, indice, totales, rechazos):
        cabecera = geografia.cabecera_para(municipio)
        if cabecera is None:
            totales['sin_cabecera'] += 1
            self.stdout.write(self.style.WARNING(
                '  fuera del padron de cabeceras: se omite'))
            return

        elementos = osm.consultar(cabecera, radio)
        if elementos is None:
            totales['sin_datos'] += 1
            self.stdout.write(self.style.WARNING(
                '  Overpass no contesto: se omite (no es que este vacio)'))
            return

        clave_municipio = geografia.normalizar(cabecera['municipio'])
        nuevos = []
        tocados = []

        for elemento in elementos:
            datos = osm.a_datos(elemento, cabecera)
            lat, lng = datos['lat'], datos['lng']

            # La puerta, primero: lo mal formado ni siquiera llega a
            # comprobar de que municipio es (§11.5).
            motivos = validacion.validar(
                nombre=datos['nombre'],
                telefono=datos['telefono'],
                lat=lat,
                lng=lng,
                municipio=datos['municipio'],
                cabecera=cabecera,
                radio_km=radio,
            )
            if motivos:
                totales['rechazados'] += 1
                for motivo in motivos:
                    rechazos[motivo] += 1
                continue

            # Aqui si hace falta punto: sin el no hay por donde asignarle
            # municipio, y este comando trabaja por circulos. (La puerta de
            # §11.5 lo permite: ahi un dato sin punto va al reporte.)
            if lat is None or lng is None:
                totales['rechazados'] += 1
                rechazos['Sin punto: no hay coordenadas.'] += 1
                continue

            # La cabecera mas cercana manda: con un radio amplio, lo que
            # queda mas cerca de otro municipio no es de este. Con el
            # radio por defecto los circulos casi no se pisan.
            destino = geografia.cabecera_mas_cercana(lat, lng, radio)
            if destino is None:
                totales['le_toca_a_otro'] += 1
                continue
            if geografia.normalizar(destino['municipio']) != clave_municipio:
                # Le toca a otro municipio, que ya lo importara. No es un
                # error: con radios grandes los circulos se pisan.
                totales['le_toca_a_otro'] += 1
                continue

            existente = validacion.duplicado(
                indice.get(clave_municipio, {}),
                datos['nombre'], lat, lng,
            )
            if existente is not None:
                totales['duplicados'] += 1
                # La categoria SI se crea aqui (el nombre viene de OSM y es
                # de fiar), pero solo si la ficha no tiene: es la misma
                # condicion con la que `enriquecer` la usaria.
                nueva = (
                    self._categoria(datos)
                    if not existente.category_id and datos['categoria']
                    else None
                )
                if validacion.enriquecer(existente, datos, categoria=nueva):
                    totales['enriquecidos'] += 1
                    # Releer: `enriquecer` dejo en la instancia la cache de
                    # "no tiene contacto" de antes de crearlo, y con ella
                    # `cumple_trio` veria el telefono que acaba de ponerse.
                    existente = Business.objects.get(pk=existente.pk)
                    tocados.append(existente)
                continue

            negocio = ingreso.crear(
                datos,
                categoria=self._categoria(datos),
                en_revision=self.en_revision,
                procedencia='importado',
            )
            nuevos.append(negocio)
            tocados.append(negocio)
            indice.setdefault(clave_municipio, {})[
                geografia.normalizar(negocio.name)] = negocio

        promovidos = pendientes.publicar_si_cumple(tocados, self.publicado)
        publicados_nuevos = sum(
            1 for n in nuevos
            if n.publication_status_id == self.publicado.id
        )

        totales['creados'] += len(nuevos)
        totales['publicados'] += len(promovidos)
        totales['quedaron_en_revision'] += len(nuevos) - publicados_nuevos

        if nuevos or promovidos:
            self.stdout.write(
                '  %d entraron, %d publicados, %d esperan en revision'
                % (len(nuevos), len(promovidos),
                   len(nuevos) - publicados_nuevos))

    # ------------------------------------------------------------------
    def _categoria(self, datos):
        """La categoria, creandola si no existe.

        Aqui SI se crea: el nombre viene de OSM y es de fiar. El canal de
        envio, en cambio, solo busca la que ya hay, porque ahi el nombre
        lo teclea una persona y una errata no debe abrirle una categoria
        nueva al sistema.
        """
        nombre = datos['categoria']
        categoria, _ = Category.objects.get_or_create(
            name=nombre,
            defaults={'slug': slugify(nombre, allow_unicode=True)},
        )
        return categoria
