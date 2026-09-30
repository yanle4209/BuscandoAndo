package com.herling.buscandoando.ui.home

import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.data.dto.BusinessDetail
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

    // ───────────── Fase 6 · GPS ─────────────

    /** ¿En qué punto está el permiso / el GPS? */
    val locationStatus: LocationStatus = LocationStatus.Idle,

    /** Coordenadas del usuario. Solo válidas cuando status == Active. */
    val myLat: Double? = null,
    val myLng: Double? = null,

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
) {
    /** Total de páginas = ceil(totalCount / PAGE_SIZE), mínimo 1. */
    val totalPages: Int
        get() = ((totalCount + PAGE_SIZE - 1) / PAGE_SIZE).coerceAtLeast(1)

    val canGoPrevious: Boolean get() = currentPage > 1 && !isLoading
    val canGoNext: Boolean get() = currentPage < totalPages && !isLoading

    /** Vacío de verdad: terminó de cargar y no hay nada que mostrar. */
    val isEmpty: Boolean get() = hasLoaded && !isLoading && businesses.isEmpty()

    /**
     * ¿El filtro por cercanía está ACTIVO?
     * Se comprueba el estado Y que haya coordenadas: si alguien deja
     * `Active` con `myLat = null`, no mandamos parámetros rotos.
     */
    val hasLocation: Boolean
        get() = locationStatus == LocationStatus.Active && myLat != null && myLng != null

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
    }
}
