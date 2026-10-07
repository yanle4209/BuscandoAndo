"""Busqueda por texto: parcial, sin tildes y a prueba de erratas.

Lo que pide quien busca (facilidad de uso primero):

* no tener que teclear el titulo entero: con "Crisostomo" tiene que
  salir "Escuela Juan Crisostomo Estrella";
* sin importar el orden ni las tildes: "estrella crisostomo" y "nunez"
  contra "Nunez de Caceres" tienen que casar igual;
* y con una letra de mas o de menos: "crisostmo" tambien.

El ``icontains`` de SQL no da ninguno de los tres: exige la subcadena
literal, asi que "nunez" no encuentra "Nunez de Caceres" y una sola
errata cierra la busqueda. Aqui se normaliza con la misma
``geografia.normalizar`` que cruza nombres en el importador y se puntua
cada candidato; al queryset solo se le recortan los ids que puntuan, asi
que su orden, su paginacion, su radio y sus annotations siguen siendo
cosas suyas.

Lo usan la API publica (``views``: listado y destacados) Y todo el
admin, por medio de la mezcla ``BusquedaAdmin``: buscar en la web y
buscar en el admin tiene que ser la misma experiencia.
"""
import difflib

from .geografia import normalizar

# Tolerancia minima para aceptar una palabra casi igual (0..1). 0.74 deja
# pasar erratas de una o dos letras ("crisostmo" contra "crisostomo" =
# 0.94) y corta los parecidos casuales ("restaurante" contra "farmacia"
# = 0.36), que es lo que evita inventar resultados.
UMBRAL = 0.74

# Por debajo de esta longitud no se busca parecido: "sol" contra "sal" es
# ruido, no una errata. A partir de cuatro letras ya se nota la diferencia.
MIN_PARECIDA = 4

# Palabras vacias del castellano. Exigirlas en la consulta haria fallar
# busquedas legitimas: "panaderia de la paz" contra un negocio que se
# llama "Panaderia Paz" se quedaria sin "de" ni "la" por medio.
VACIAS = {
    'a', 'al', 'con', 'de', 'del', 'e', 'el', 'en', 'la', 'las', 'los',
    'o', 'of', 'para', 'por', 'sin', 'sobre', 'the', 'un', 'una', 'y',
}

# Tope de palabras tecleadas: mas de ocho y la consulta ya no es de
# alguien que busca, es de alguien que pega.
MAX_TOKENS = 8

# Los campos con los que busca la API publica: nombre, categoria y las
# dos descripciones, que son los mismos con los que busca la ficha.
CAMPOS_NEGOCIO = (
    'name',
    'category__name',
    'short_description',
    'description',
)


def tokens_de(texto):
    """Las palabras con las que se busca, ya normalizadas.

    Las vacias se saltan, pero si la consulta solo las tiene ("de la")
    se buscan ellas: mejor eso que no buscar nada.
    """
    palabras = normalizar(texto)[:80].split()
    importantes = [p for p in palabras if p not in VACIAS][:MAX_TOKENS]
    return importantes or palabras[:MAX_TOKENS]


def _parecida(token, palabras):
    """Si alguna palabra de la lista es casi el ``token``."""
    if not palabras:
        return False
    return bool(difflib.get_close_matches(token, palabras, n=1, cutoff=UMBRAL))


def _texto(valor):
    """Un valor de la base como texto normalizado.

    Llega ``None`` cuando el campo es opcional (la categoria, sobre
    todo) y, en los JSON, como dict o lista: ``str`` y a normalizar.
    """
    if valor is None:
        return ''
    if not isinstance(valor, str):
        valor = str(valor)
    return normalizar(valor)


def puntuacion(textos, tokens):
    """Puntuacion 0..1 del negocio, o ``None`` si le falta algun token.

    Los ``textos`` llegan ya normalizados, que es lo que hace que las
    tildes dejen de importar. Cada palabra tecleada tiene que aparecer
    en alguno de ellos, o parecida a alguna de sus palabras.
    """
    palabras = [palabra for texto in textos for palabra in texto.split()]
    juntos = ' '.join(textos)

    puntos = 0.0
    for token in tokens:
        if token in juntos:
            puntos += 1.0
        elif len(token) >= MIN_PARECIDA and _parecida(token, palabras):
            puntos += 0.5
        else:
            return None
    return puntos / len(tokens)


def filtrar_por_texto(qs, texto, campos=CAMPOS_NEGOCIO):
    """``qs`` recortada a los negocios que casan con ``texto``.

    Se puntua en Python sobre los ``campos`` dados (rutas de consulta
    Django, como las de ``search_fields``) porque SQL no sabe de tildes
    ni de erratas. El recorte es un ``filter(id__in=...)`` sobre el
    propio queryset, no una lista reconstruida: asi no se pierde su
    orden, su paginacion ni sus annotations.

    El queryset que entra debe venir ya recortado por radio y demas
    filtros, que es lo que hace la vista: el precio de puntuar en
    Python se paga sobre lo que ya estaba, no sobre la base entera.
    """
    tokens = tokens_de(texto)
    if not tokens:
        return qs.none()

    # prefetch_related(None): los prefetch no aplican a una consulta de
    # valores y estorban, asi que se vacian antes de puntuar.
    filas = qs.prefetch_related(None).values_list('id', *campos)
    ids = [
        fila[0]
        for fila in filas
        if puntuacion([_texto(valor) for valor in fila[1:]], tokens) is not None
    ]
    return qs.filter(id__in=ids)


class BusquedaAdmin:
    """El buscador de un ModelAdmin, con las mismas reglas que la web.

    El ``search_fields`` por defecto busca con ``icontains`` campo a
    campo, y en el admin eso duele mas que en la web: con mas de 16000
    fichas, "nunez" no encuentra "Nunez de Caceres", "crisostomo" no
    encuentra "Escuela Juan Crisostomo Estrella" y una sola errata deja
    la busqueda vacia. Aqui la consulta pasa por
    :func:`filtrar_por_texto` con los MISMOS campos que declara
    ``search_fields`` del ModelAdmin, asi que no hay nada que declarar
    dos veces: basta con heredar de esta clase ademas de
    ``admin.ModelAdmin``.

    ``search_fields`` sigue siendo obligatorio: es lo que enseña la
    caja de busqueda y lo que usan ademas los desplegables de
    autocompletado. Sin campo, o sin nada tecleado, manda Django.
    """

    def get_search_results(self, request, queryset, search_term):
        if not (search_term or '').strip():
            return super().get_search_results(request, queryset, search_term)

        campos = tuple(
            campo.lstrip('^~=')
            for campo in getattr(self, 'search_fields', [])
        )
        if not campos:
            return super().get_search_results(request, queryset, search_term)

        # False: el filtro es sobre el propio queryset (id__in), sin
        # duplicados que exigir con distinct().
        return filtrar_por_texto(queryset, search_term, campos), False
