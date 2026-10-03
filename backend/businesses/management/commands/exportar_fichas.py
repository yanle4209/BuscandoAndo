"""Escribe las fichas a un JSONL para llevarlas a otra base (R5).

    python manage.py exportar_fichas
    python manage.py exportar_fichas salida.ndjson
    python manage.py exportar_fichas --municipio Moca
    python manage.py exportar_fichas --excluir Moca

Es la primera mitad de la opción B de "como llegan los datos del pais
a produccion": se importa aqui, se exporta, y en la otra base se corre
``cargar_fichas`` con el archivo. No se consulta Overpass en la maquina
de produccion, y sobre todo **no se pisa nada**: lo que ya este alla se
cruza y se enriquece (§10-d).

El formato lo define ``businesses.portar``, no aqui — este comando solo
recorre fichas y las va escribiendo.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from businesses import geografia, portar
from businesses.models import Business

# Donde cae si no se dice nada. Junto a las cabeceras: es la otra fuente
# estatica con que se levanta una base desde cero.
SALIDA_POR_DEFECTO = settings.BASE_DIR / 'data' / 'fichas_nacionales.ndjson.gz'


class Command(BaseCommand):
    help = ('Exporta las fichas a un JSONL (o .gz) con el formato que '
            'lee `cargar_fichas`.')

    def add_arguments(self, parser):
        parser.add_argument(
            'salida', nargs='?', default=str(SALIDA_POR_DEFECTO),
            help='Archivo a escribir. Si acaba en .gz se comprime '
                 '(por defecto %s).' % SALIDA_POR_DEFECTO,
        )
        parser.add_argument(
            '--municipio',
            help='Solo las fichas de este municipio. Con uno solo se puede '
                 'probar la carga sin subir el pais entero.',
        )
        parser.add_argument(
            '--excluir', default='',
            help='Municipios que no viajan, separados por coma. Para no '
                 'exportar el que la base de destino ya tiene trabajado a '
                 'mano (Moca, en el caso de produccion).',
        )

    def handle(self, *args, **opciones):
        salida = Path(opciones['salida'])
        # Se normaliza igual que en el resto del sistema: minusculas y sin
        # acentos, para que "Moca" y "MÓCA" quiten lo mismo.
        excluir = {
            geografia.normalizar(m)
            for m in (opciones['excluir'] or '').split(',')
            if m.strip()
        }
        if excluir:
            self.stdout.write('No viajan: %s' % ', '.join(sorted(excluir)))

        consulta = (
            Business.objects
            .select_related(
                'location', 'contact', 'category', 'operational_status',
            )
            .prefetch_related('hours')
            # Agrupado por municipio: `cargar_fichas` cierra un municipio
            # en cuanto empieza el siguiente, y asi su resumen sale una
            # linea por municipio en vez de troceado.
            .order_by('location__municipality', 'name')
        )
        if opciones['municipio']:
            consulta = consulta.filter(
                location__municipality__iexact=opciones['municipio'],
            )

        escritas = 0
        sin_ubicacion = 0
        excluidas = 0
        salida.parent.mkdir(parents=True, exist_ok=True)
        with portar.abrir_texto(salida, 'wt') as fh:
            for negocio in consulta.iterator(chunk_size=500):
                datos = portar.datos_de(negocio)
                if not (datos['municipio'] or '').strip():
                    # Sin municipio no hay cabecera que la reciba al
                    # cargar, y cargarla seria crear una ficha que nadie
                    # puede buscar. Se avisa, no se oculta.
                    sin_ubicacion += 1
                    continue
                if geografia.normalizar(datos['municipio']) in excluir:
                    # Moca ya esta en la base de destino, hecha a mano: lo
                    # que salga de aqui solo puede ser peor que lo que hay
                    # alla (§10-d). Se queda fuera.
                    excluidas += 1
                    continue
                fh.write(portar.a_linea(datos) + '\n')
                escritas += 1

        if not escritas:
            raise CommandError('No salio ninguna ficha en %s' % salida)

        self.stdout.write(self.style.SUCCESS(
            '%d fichas escritas en %s' % (escritas, salida)))
        if excluidas:
            self.stdout.write('  %d de municipios excluidos se quedaron '
                              'fuera: ya estan en la base de destino.'
                              % excluidas)
        if sin_ubicacion:
            self.stdout.write(self.style.WARNING(
                '  %d sin municipio se quedaron fuera: no tienen cabecera '
                'donde caer.' % sin_ubicacion))
        self.stdout.write('  Tamano: %.1f MB'
                          % (salida.stat().st_size / 1048576))
        self.stdout.write('  Siguiente paso: `manage.py cargar_fichas %s`'
                          % salida)
