"""Carga las fichas de un JSONL en esta base, cruzando en vez de pisar (R5).

    python manage.py cargar_fichas data/fichas_nacionales.ndjson.gz
    python manage.py cargar_fichas fichas.ndjson --omitir Moca

La segunda mitad de la opcion B: lo que ya hay aqui manda. Cada linea
pasa por ``masivo.Lote``, el mismo camino que usa ``importar_municipio``
—validar en la puerta, cruzar contra lo que ya existe (§10-d) y publicar
solo el que cumpla el trio (§10-f)—, asi que:

* **se puede correr dos veces**: la segunda no crea nada, solo enriquece;
* **no pisa**: si la ficha ya tiene telefono, se queda el de aqui, y el
  que trae el archivo se ignora (§10-d: nunca sobrescribir);
* **una ficha creada a mano no se publica sola**, aunque el archivo diga
  que estaba publicada: quien publica es el admin (VISION.md);
* **un municipio se puede dejar fuera** con ``--omitir``, para cuando la
  base de destino ya tiene ese municipio trabajado a mano.

Si se corta a mitad, se vuelve a correr: al ser idempotente, repetirlo
termina de cargar lo que falte sin duplicar lo que ya entro.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from operational_status.models import OperationalStatus
from publication_status.models import PublicationStatus

from businesses import geografia, masivo, portar


class Command(BaseCommand):
    help = ('Carga las fichas de un JSONL escrito por `exportar_fichas`, '
            'cruzando contra lo que ya existe en vez de pisarlo.')

    def add_arguments(self, parser):
        parser.add_argument(
            'entrada',
            help='JSONL (o .gz) que escribio `exportar_fichas`.',
        )
        parser.add_argument(
            '--omitir', default='',
            help='Municipios que no se tocan, separados por coma. Para '
                 'dejar intacto el que la base de destino ya tenia.',
        )
        parser.add_argument(
            '--radio', type=float, default=geografia.RADIO_KM,
            help='Radio con que se comprueba que el punto cae en su '
                 'municipio, en km (por defecto %g, el de R1).'
                 % geografia.RADIO_KM,
        )

    def handle(self, *args, **opciones):
        radio = opciones['radio']
        if radio <= 0:
            raise CommandError('--radio tiene que ser un numero positivo.')

        entrada = Path(opciones['entrada'])
        if not entrada.exists():
            raise CommandError('No existe el archivo: %s' % entrada)

        omitir = {
            geografia.normalizar(m)
            for m in (opciones['omitir'] or '').split(',')
            if m.strip()
        }
        if omitir:
            self.stdout.write('Se omiten: %s' % ', '.join(sorted(omitir)))

        # Sin estos cuatro no hay donde poner lo que entre, igual que en
        # el importador.
        publicado = PublicationStatus.objects.get(slug='publicado')
        en_revision = PublicationStatus.objects.get(slug='en-revision')
        for slug in ('abierto', 'cerrado'):
            if not OperationalStatus.objects.filter(slug=slug).exists():
                raise CommandError(
                    'Falta el estado operativo "%s": cargalo antes de '
                    'cargar.' % slug
                )

        lote = masivo.Lote(radio=radio, en_revision=en_revision,
                           publicado=publicado)
        # Cabeceras ya vistas: son 158 y cada linea volveria a recorrerlas.
        cabeceras = {}

        leidos = 0
        en_este = 0
        omitidos = 0
        numero = 0
        actual = None  # clave normalizada del municipio que se esta leyendo

        with portar.abrir_texto(entrada, 'rt') as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                registro = portar.desde_linea(linea)
                leidos += 1

                clave = geografia.normalizar(registro.get('municipio'))
                provincia = geografia.normalizar(registro.get('provincia'))
                if clave != actual:
                    # El archivo sale agrupado por municipio (asi lo
                    # escribe `exportar_fichas`): el cambio de municipio
                    # es lo que cierra el anterior. Si no lo estuviera,
                    # el resultado seria el mismo, solo que el resumen
                    # saldria troceado.
                    if actual is not None:
                        self._cerrar(lote, en_este)
                    actual = clave
                    en_este = 0
                    numero += 1
                    self.stdout.write(
                        '[%d] %s' % (numero,
                                     registro.get('municipio') or '(sin municipio)'))
                en_este += 1

                if clave in omitir:
                    omitidos += 1
                    continue

                if (clave, provincia) not in cabeceras:
                    cabeceras[(clave, provincia)] = geografia.cabecera_para(
                        registro.get('municipio'), registro.get('provincia'),
                    )
                cabecera = cabeceras[(clave, provincia)]
                if cabecera is None:
                    # Sin cabecera no hay con que comprobar que el punto
                    # cae en el municipio que dice ser (§11.5).
                    lote.totales['sin_cabecera'] += 1
                    continue

                lote.agregar(registro, cabecera)

            if actual is not None:
                self._cerrar(lote, en_este)

        if not leidos:
            raise CommandError('El archivo no tiene ninguna ficha: %s' % entrada)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('RESULTADO'))
        self.stdout.write('  %-22s %d' % ('leidos', leidos))
        if omitidos:
            self.stdout.write('  %-22s %d' % ('omitidos', omitidos))
        for clave_total in ('creados', 'publicados', 'quedaron_en_revision',
                            'duplicados', 'enriquecidos', 'rechazados',
                            'le_toca_a_otro', 'sin_cabecera'):
            self.stdout.write('  %-22s %d'
                              % (clave_total, lote.totales[clave_total]))
        if lote.rechazos:
            self.stdout.write('  motivos:')
            for motivo, cantidad in lote.rechazos.most_common():
                self.stdout.write('    %d  %s' % (cantidad, motivo))

    # ------------------------------------------------------------------
    def _cerrar(self, lote, leidos):
        """Cierra el municipio que se acaba de leer e imprime su linea."""
        entraron, publicados, esperan = lote.publicar()
        self.stdout.write(
            '  %d leidos, %d entraron, %d publicados, %d esperan en revision'
            % (leidos, entraron, publicados, esperan))
