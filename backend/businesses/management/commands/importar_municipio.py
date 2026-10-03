"""Importa los negocios de un municipio desde OpenStreetMap (R5).

    python manage.py importar_municipio Moca
    python manage.py importar_municipio --todos
    python manage.py importar_municipio Moca --radio 12

Este comando solo **trae**: una consulta Overpass por cabecera. Lo que
hace despues con cada candidato —validar en la puerta, cruzar contra lo
que ya existe, crear el resto como `en-revision` y publicar el que cumpla
el trio— vive en ``businesses.masivo.Lote``, que comparte con
``cargar_fichas``. Si cada comando hiciera lo suyo, lo que entrara por
OpenStreetMap y lo que se trajera de otra base no seria comparable, y es
justo la comparabilidad de lo que esta publicado lo que §10-i quiere.

En resumen, el orden que impone el lote:

1. **valida en la puerta** — lo mal formado se descarta con su motivo y
   no llega a estar pendiente de nada (§11.5);
2. **cruza contra lo que ya existe** — si es un duplicado, se le rellena
   lo que le falta a la ficha que ya esta; nunca se crea una segunda
   (§10-d: OSM trae telefonos que en muchos casos nosotros no tenemos);
3. crea el resto como `en-revision` con `procedencia='importado'`;
4. y de lo que acaba de crear, **publica el que cumpla el trio** (§10-f:
   nombre + telefono + punto). Lo que no lo cumple **no se descarta**:
   se queda en `en-revision` y sale en el reporte de §11.1.

Las fichas creadas a mano (`procedencia='manual'`) nunca se publican solas
ni siquiera si cumplen el trio: eso sigue siendo el admin (VISION.md).
"""
from django.core.management.base import BaseCommand, CommandError

from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from businesses import geografia, masivo, osm


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
        publicado = PublicationStatus.objects.get(slug='publicado')
        en_revision = PublicationStatus.objects.get(slug='en-revision')
        for slug in ('abierto', 'cerrado'):
            if not OperationalStatus.objects.filter(slug=slug).exists():
                raise CommandError(
                    'Falta el estado operativo "%s": cargalo antes de '
                    'importar.' % slug
                )

        # Un solo lote para la corrida entera: asi lo creado en el primer municipio
        # se cruza ya en el segundo.
        lote = masivo.Lote(radio=radio, en_revision=en_revision,
                           publicado=publicado)

        for numero, municipio in enumerate(objetivos, 1):
            self.stdout.write('[%d/%d] %s'
                              % (numero, len(objetivos), municipio))
            self._importar(municipio, lote)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('RESULTADO'))
        self._imprimir_totales(lote)

    # ------------------------------------------------------------------
    def _importar(self, municipio, lote):
        """Una consulta Overpass, y todo lo que salga de ella al lote."""
        cabecera = geografia.cabecera_para(municipio)
        if cabecera is None:
            lote.totales['sin_cabecera'] += 1
            self.stdout.write(self.style.WARNING(
                '  fuera del padron de cabeceras: se omite'))
            return

        elementos = osm.consultar(cabecera, lote.radio)
        if elementos is None:
            lote.totales['sin_datos'] += 1
            self.stdout.write(self.style.WARNING(
                '  Overpass no contesto: se omite (no es que este vacio)'))
            return

        for elemento in elementos:
            lote.agregar(osm.a_datos(elemento, cabecera), cabecera)

        entraron, publicados, _esperan = lote.publicar()
        if entraron or publicados:
            self.stdout.write(
                '  %d entraron, %d publicados, %d esperan en revision'
                % (entraron, publicados, _esperan))

    def _imprimir_totales(self, lote):
        for clave in ('creados', 'publicados', 'quedaron_en_revision',
                      'duplicados', 'enriquecidos', 'rechazados',
                      'le_toca_a_otro', 'sin_datos', 'sin_cabecera'):
            self.stdout.write('  %-22s %d' % (clave, lote.totales[clave]))
        if lote.rechazos:
            self.stdout.write('  motivos:')
            for motivo, cantidad in lote.rechazos.most_common():
                self.stdout.write('    %d  %s' % (cantidad, motivo))
