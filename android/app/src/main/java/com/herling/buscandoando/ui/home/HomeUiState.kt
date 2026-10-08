package com.herling.buscandoando.ui.home

import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.data.dto.BusinessDetail
import com.herling.buscandoando.core.data.dto.Cabecera
import com.herling.buscandoando.core.data.dto.Category

/**
 * FASE 6 · Estado del permiso y del GPS.
 *
 * Es un enum en vez de tres `Boolean` sueltos porque así es
 * IMPOSIBLE estar a la vez "Locating" y "Denied". La UI hace un
 * `when` exhaustivo y el compilador le recuerda si falta un caso.
 */
enum class LocationStatus {
    /** Nunca se pidió nada. El botón de ubicación está en reposo. */
    Idle,

    /** Esperando el fix del GPS (o el resultado del diálogo). */
    Locating,

    /** Tenemos coordenadas: el filtro por cercanía está ACTIVO. */
    Active,

    /** Sin permiso o sin GPS: mostramos el aviso con las salidas. */
    Denied,
}


/**
 * Estado completo de la pantalla Home.
 *
 * Es el "contrato con la pantalla": TODO lo que la UI necesita para
 * dibujarse vive aquí. NO es un DTO — no viaja por HTTP, por eso
 * NO lleva @Serializable.
 *
 * Regla de oro: TODOS los campos tienen valor por defecto, para que
 * la pantalla pueda dibujarse ANTES de que la primera respuesta llegue.
 *
 * Equivalente en React:
 *
 *   const [query, setQuery] = useState("");
 *   const [items, setItems] = useState([]);
 *   ...
 *   //  ->  un solo objeto inmutable que se reemplaza completo
 */
data class HomeUiState(
    /** Texto que el usuario va escribiendo en la caja de búsqueda. */
    val query: String = "",

    /** Las categorías del API (15) para pintar los chips. */
    val categories: List<Category> = emptyList(),

    /** Categoría elegida. null = "Todas" (sin filtro). */
    val selectedCategory: Category? = null,

    /** Las tarjetas de la página ACTUAL (máx. 12). */
    val businesses: List<Business> = emptyList(),

    /** true mientras la petición está en vuelo -> muestra el spinner. */
    val isLoading: Boolean = false,

    /** null = todo bien. Con texto = mostrar el aviso + botón reintentar. */
    val errorMessage: String? = null,

    /** ¿Ya cargó al menos una vez? Para distinguir "vacío" de "sin buscar". */
    val hasLoaded: Boolean = false,

    /** Página visible (base 1). */
    val currentPage: Int = 1,

    /** Total real de resultados del API (no de esta página). */
    val totalCount: Int = 0,

    // ───────────── Fase 4 · detalle en hoja modal ─────────────

    /**
     * slug de la tarjeta que el usuario tocó.
     * null  = la hoja está CERRADA (no componemos nada).
     * otro  = la hoja está ABIERTA y ese es el negocio a pedir.
     */
    val detailSlug: String? = null,

    /**
     * El detalle ya descargado. Forma ANIDADA (location/contact/hours),
     * NO la plana de la lista. null mientras carga o si falló.
     */
    val detail: BusinessDetail? = null,

    /** true mientras se pide GET /api/businesses/<slug>/. */
    val detailLoading: Boolean = false,

    /** null = todo bien. Con texto = la hoja muestra el error. */
    val detailError: String? = null,

    // ───────────── Fase 8 · la máquina de la web ─────────────

    /** ¿En qué punto está el permiso / el GPS? */
    val locationStatus: LocationStatus = LocationStatus.Idle,

    /**
     * Última posición GPS conocida (equivale a `pos` de Home.jsx).
     *
     * OJO: NO es el punto de consulta. Ese es `punto`. Están separados
     * porque al andar la posición cambia sin mover el círculo que se
     * está consultando (y al revés: eliges un municipio a 20 km y el
     * punto se va sin que te muevas).
     */
    val pos: Punto? = null,

    /**
     * Centro del círculo de 5 km que se está consultando (equivale a
     * `punto` de Home.jsx). null = sin punto activo = NO se consulta
     * NADA y la pantalla se queda en portada (R1.1).
     */
    val punto: Punto? = null,

    /** Municipio elegido o punto tocado en el mapa (equivale a `destino`). */
    val destino: Punto? = null,

    /** Espera (S0) | Gps (S1) | Destino (S2): ver [SearchMode]. */
    val mode: SearchMode = SearchMode.Espera,

    /** El destino viene del almacén, no de una elección (R3.4). */
    val restaurado: Boolean = false,

    /** Ya estuvo dentro del destino: habilita el reset de R3.2. */
    val llego: Boolean = false,

    /**
     * ¿Se ha hecho la primera consulta? false = portada.
     *
     * Se separa de `punto` a propósito: el GPS puede darte coordenadas
     * y seguir mostrándose la portada hasta que el usuario haga algo
     * explícito (buscar, elegir municipio o tocar "Mi ubicación"),
     * exactamente igual que en la web.
     */
    val haBuscado: Boolean = false,

    /**
     * Clave "Provincia~Municipio" del selector (equivale a
     * `municipioClave`). "" = el selector muestra "Elige tu municipio".
     */
    val municipioClave: String = "",

    /** Las 158 cabeceras del API, para el selector de municipio. */
    val cabeceras: List<Cabecera> = emptyList(),

    /** true si GET /api/cabeceras/ falló (el selector lo avisa). */
    val cabecerasError: Boolean = false,

    // ───────────── Fase 7 · destacados ─────────────

    /**
     * Respuesta de GET /api/businesses/featured-by-search/.
     *
     * Son como máximo 3 tarjetas que la web pinta POR ENCIMA de los
     * resultados (`searchFeatured` en Home.jsx). Aquí lo mismo: una
     * fila que solo aparece si hay algo que mostrar.
     *
     * Vacío cuando (a) no hay filtros —el endpoint devuelve [] por
     * contrato—, (b) ningún destacado coincide, o (c) la llamada
     * secundaria falla. En los tres casos la fila simplemente no se
     * dibuja: es contenido de "si hay", no debe romper la pantalla.
     */
    val featuredBySearch: List<Business> = emptyList(),

    /**
     * true si GET /api/categories/ falló.
     *
     * Los chips son "nice to have" y su error se traga a propósito
     * (si no, un servidor dormido dejaría la pantalla sin categorías
     * y sin aviso). Con este flag la UI puede decirlo con un snackbar.
     */
    val categoriesError: Boolean = false,

    // ───────────── Fase 9 · botón "Corregir" ─────────────
    //
    // Es el formulario de CorrectionModal.jsx trasladado a estados:
    // `correccionId != null` equivale a "el modal está abierto" (en la
    // web es `correccionBiz`). La red vive en el ViewModel; aquí solo
    // se pinta lo que diga el estado.

    /** id del negocio que se quiere corregir; null = modal cerrado. */
    val correccionId: Int? = null,

    /** Nombre del negocio, para "…dato de %1$s está mal?". */
    val correccionNombre: String = "",

    /** true mientras el POST está en vuelo (fase "enviando"). */
    val correccionEnviando: Boolean = false,

    /** true cuando el backend contestó 201 (fase "listo"). */
    val correccionEnviada: Boolean = false,

    /**
     * Motivo del fallo al enviar.
     *
     *  null  → no hubo error
     *  ""    → hubo error sin detalle legible (el modal pinta el
     *          genérico "No se pudo enviar el aviso…")
     *  texto → el mensaje que devolvió el backend (p. ej. el de los
     *          10 caracteres que exige validate_mensaje)
     */
    val correccionError: String? = null,
) {
    /** Total de páginas = ceil(totalCount / PAGE_SIZE), mínimo 1. */
    val totalPages: Int
        get() = ((totalCount + PAGE_SIZE - 1) / PAGE_SIZE).coerceAtLeast(1)

    val canGoPrevious: Boolean get() = currentPage > 1 && !isLoading
    val canGoNext: Boolean get() = currentPage < totalPages && !isLoading

    /** Vacío de verdad: terminó de cargar y no hay nada que mostrar. */
    val isEmpty: Boolean get() = hasLoaded && !isLoading && businesses.isEmpty()

    /**
     * ¿Hay POSICIÓN GPS conocida? (equivale a `estado.pos != null`)
     *
     * Es lo que enciende el icono del botón de ubicación. NO decide lo
     * que se consulta: eso es [hasPunto].
     */
    val hasLocation: Boolean get() = pos != null

    /**
     * ¿Hay punto activo que consultar? (equivale a `estado.punto != null`)
     *
     * Sin punto no se manda ni un byte al API (R1.1) y la pantalla se
     * queda en portada.
     */
    val hasPunto: Boolean get() = punto != null

    /** "Elige tu municipio o activa tu ubicación para empezar" (R1.1). */
    val sinPunto: Boolean get() = punto == null

    /**
     * Etiqueta del municipio elegido, o null si no lo hay.
     * "Moca · Espaillat" a partir de la clave "Espaillat~Moca".
     */
    val municipioEtiqueta: String?
        get() {
            val partes = municipioClave.split('~')
            if (partes.size != 2 || partes[1].isBlank()) return null
            return "${partes[1]} · ${partes[0]}"
        }

    companion object {
        /** 12 por página = la cuadrícula 4x3 de la web. */
        const val PAGE_SIZE = 12

        /**
         * Radio de búsqueda en KILOMETROS: FIJO, no es un filtro.
         *
         * Decisión R1.3: la búsqueda es "a 5 km de donde estés" en
         * TODAS las plataformas, así que el chip de 2 km se ha ido —
         * con dos radios distintos la web y la app dejan de verse igual
         * para la misma persona.
         *
         * El valor lo fija la API de todos modos (`parse_radio` lo
         * recorta a 5): mandar radius=10 devuelve lo mismo que radius=5.
         * Aquí está para los logs y para el texto de la barra.
         */
        const val RADIO_KM = 5

        /**
         * R1.a · disparo 3: refrescar cuando el usuario se aleja ≥ 0,5 km
         * del último punto consultado (UMBRAL_MOV_KM de Home.jsx).
         */
        const val UMBRAL_MOV_KM = 0.5

        /**
         * R1.a · mínimo 30 s entre refrescos AUTOMÁTICOS por movimiento
         * (THROTTLE_MS de Home.jsx). Los cambios explícitos de punto
         * (llegada, municipio, primera búsqueda, "Mi ubicación") NO se
         * limitan: si no, el refresco de llegada se descartaría y
         * te quedarías mirando resultados viejos.
         */
        const val THROTTLE_MS = 30_000L
    }
}
