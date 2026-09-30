package com.herling.buscandoando.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import android.util.Log
import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.data.dto.BusinessDetail
import com.herling.buscandoando.core.data.dto.Category
import com.herling.buscandoando.core.network.ApiClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * ViewModel de la pantalla Home.
 *
 * Responsabilidad: ser el ÚNICO punto que toca la red y el estado.
 * La UI solo emite eventos y dibuja el estado — nunca hace fetch.
 *
 *   React                                   Aquí
 *   ─────────────────────────────────       ──────────────────────────────
 *   const [state, setState] = useState(..)  _uiState = MutableStateFlow(..)
 *   setState({...})                         _uiState.update { it.copy(..) }
 *   useEffect(() => fetch(), [])            init { load() }
 *   return state                            val uiState: StateFlow<..>
 *
 * `viewModelScope` es una corrutina ligada al ciclo de vida del
 * ViewModel: si el usuario sale de la pantalla, las peticiones en
 * vuelo se cancelan SOLEAS (no quedan zombis).
 *
 * `MutableStateFlow` es privado ("_") y solo se expone como
 * `StateFlow` ("solo lectura") — así NADIE desde fuera puede hacer
 * update() del estado. Se llama "encapsulamiento".
 */
class HomeViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    /** Cancela la búsqueda anterior si se lanza otra (evita respuestas cruzadas). */
    private var searchJob: Job? = null

    /** Cancela el detalle anterior (se cierra la hoja o se pide otro). */
    private var detailJob: Job? = null

    init {
        loadCategories()
        search(page = 1)
    }

    // ─────────────── EVENTOS que la UI puede emitir ───────────────

    /** El usuario escribe en la caja. Solo actualiza el texto, NO busca. */
    fun onQueryChange(value: String) {
        _uiState.update { it.copy(query = value) }
    }

    /** Enter en el teclado o botón de buscar. */
    fun onSearch() = search(page = 1)

    /** Tocó un chip de categoría. Cambia el filtro Y recarga. */
    fun onCategorySelected(category: Category?) {
        _uiState.update { it.copy(selectedCategory = category) }
        search(page = 1)
    }

    fun onNextPage() {
        val s = _uiState.value
        if (s.canGoNext) search(page = s.currentPage + 1)
    }

    fun onPreviousPage() {
        val s = _uiState.value
        if (s.canGoPrevious) search(page = s.currentPage - 1)
    }

    /**
     * Botón "Reintentar" del banner de error.
     *
     * ⚠️ También reintenta las CATEGORÍAS si no llegaron. De lo
     * contrario, si el servidor estaba dormido al arrancar, los chips
     * de categoría quedarían invisibles para siempre, porque
     * `loadCategories()` traga su error a propósito y nadie lo
     * volvía a pedir.
     */
    fun onRetry() {
        if (_uiState.value.categories.isEmpty()) loadCategories()
        search(page = _uiState.value.currentPage)
    }

    // ─────────────── Fase 4 · DETALLE (hoja modal) ───────────────

    /**
     * Tocó una tarjeta → abre la hoja y pide el detalle.
     *
     * Si YA lo tenemos cargado, no volvemos a pedirlo (mini-caché).
     */
    fun onBusinessSelected(slug: String) {
        val current = _uiState.value
        if (current.detailSlug == slug && current.detail != null) return

        _uiState.update {
            it.copy(detailSlug = slug, detail = null, detailLoading = true, detailError = null)
        }
        loadDetail(slug)
    }

    /** El usuario cerró la hoja (tap afuera o botón): cancela y limpia. */
    fun onCloseDetail() {
        detailJob?.cancel()
        _uiState.update {
            it.copy(detailSlug = null, detail = null, detailLoading = false, detailError = null)
        }
    }

    /** Botón "Reintentar" DENTRO de la hoja. */
    fun onRetryDetail() {
        _uiState.value.detailSlug?.let { loadDetail(it) }
    }

    /**
     * GET /api/businesses/<slug>/
     *
     * El `if (_uiState.value.detailSlug == slug)` es el patrón
     * "descartar respuestas obsoletas": si mientras cargaba el usuario
     * cerró la hoja o tocó OTRA tarjeta, esta respuesta ya no interesa
     * y NO debe pintarse. En React sería un flag de cancelación.
     */
    private fun loadDetail(slug: String) {
        detailJob?.cancel()
        detailJob = viewModelScope.launch {
            _uiState.update { it.copy(detailLoading = true, detailError = null) }

            try {
                val detail = ApiClient.api.getBusiness(slug)
                if (_uiState.value.detailSlug == slug) {
                    _uiState.update { it.copy(detailLoading = false, detail = detail) }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (_uiState.value.detailSlug == slug) {
                    _uiState.update {
                        it.copy(
                            detailLoading = false,
                            detailError = e.message ?: e::class.simpleName ?: "Error desconocido",
                        )
                    }
                }
            }
        }
    }

    // ───────────── Fase 6 · GPS ─────────────

    /**
     * El usuario tocó el botón de ubicación.
     *
     * Solo marcamos "buscando": el PERMISO lo pide la UI (necesita un
     * diálogo del sistema y una explicación), y las coordenadas las
     * obtiene la UI y nos las devuelve con `onLocationAcquired`.
     */
    fun onStartLocating() {
        _uiState.update { it.copy(locationStatus = LocationStatus.Locating) }
    }

    /** La UI ya tiene permiso y el GPS respondió con un fix. */
    fun onLocationAcquired(lat: Double, lng: Double) {
        _uiState.update {
            it.copy(locationStatus = LocationStatus.Active, myLat = lat, myLng = lng)
        }
        search(page = 1)
    }

    /**
     * No hubo permiso o no hubo GPS.
     * Un único estado "Denied" para ambas causas: el aviso de la UI
     * ofrece las dos salidas (reintentar / ajustes) y las cubre.
     */
    fun onLocationFailed() {
        _uiState.update {
            it.copy(locationStatus = LocationStatus.Denied, myLat = null, myLng = null)
        }
    }

    /** Apaga el filtro por cercanía y vuelve a la búsqueda normal. */
    fun onClearLocation() {
        _uiState.update {
            it.copy(locationStatus = LocationStatus.Idle, myLat = null, myLng = null)
        }
        search(page = 1)
    }

    // ─────────────── Acceso a datos ───────────────

    /**
     * GET /api/businesses/?page=&page_size=12&text=&category=
     *
     * `ifBlank { null }` es clave: Retrofit NO agrega los parámetros
     * cuyo valor es null, así que una búsqueda vacía manda
     * /api/businesses/?page=1&page_size=12  (sin &text=)
     */
    private fun search(page: Int) {
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }

            try {
                val current = _uiState.value
                val text = current.query.trim().ifBlank { null }
                val catId = current.selectedCategory?.id

                // Fase 6: deja en logcat QUÉ mandamos al API (lat/lng/radius).
                Log.d(
                    "BuscandoAndo",
                    "search page=$page text='${current.query}' cat=${current.selectedCategory?.id} " +
                        "lat=${current.myLat} lng=${current.myLng} " +
                        "radio=${HomeUiState.RADIO_KM}km cerca=${current.hasLocation}",
                )

                // ── Fase 7: los DESTACADOS viajan EN PARALELO ──
                //
                // `async` lanza la corrutina YA mismo (es "eager"), así que
                // mientras `getBusinesses` se queda esperando a la red, este
                // otro trabajo corre solo. Es el equivalente a:
                //
                //   const [res, feat] = await Promise.all([fetch(..), fetch(..)])
                //
                // Si no hay filtros el endpoint devuelve [] por contrato, así
                // que ni lo pedimos: ahorramos una petición en la carga
                // inicial y en cada página.
                val featuredJob = if (text == null && catId == null) {
                    null
                } else {
                    async { fetchFeaturedFor(text, catId, current.myLat, current.myLng) }
                }

                val response = ApiClient.api.getBusinesses(
                    page = page,
                    pageSize = HomeUiState.PAGE_SIZE,
                    text = text,
                    category = catId,
                    // ── Fase 6: filtro por cercanía ──
                    // Si no hay ubicación, los tres vienen en null y
                    // Retrofit los OMITE de la URL (mismo truco que
                    // ifBlank { null } de "text").
                    lat = current.myLat,
                    lng = current.myLng,
                    radius = if (current.hasLocation) HomeUiState.RADIO_KM.toDouble() else null,
                )

                // Siempre llegamos aquí: `featuredJob` nunca falla (ver abajo).
                val featured = featuredJob?.await() ?: emptyList()

                _uiState.update {
                    it.copy(
                        isLoading = false,
                        businesses = response.results,
                        totalCount = response.count,
                        currentPage = page,
                        hasLoaded = true,
                        featuredBySearch = featured,
                    )
                }
            } catch (e: CancellationException) {
                // La corrutina fue cancelada a propósito: propagar, NO tragar.
                throw e
            } catch (e: Exception) {
                // Cualquier fallo (sin internet, 500, JSON raro...)
                // se convierte en estado que la UI sabe pintar.
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = e.message ?: e::class.simpleName ?: "Error desconocido",
                    )
                }
            }
        }
    }

    /**
     * GET /api/businesses/featured-by-search/  (Fase 7)
     *
     * Es una llamada SECUNDARIA: si falla, la búsqueda principal NO
     * debe caer. Por eso esta función JAMÁS lanza hacia arriba —
     * devuelve una lista (vacía si algo malo pasa) y solo vuelve a
     * lanzar la CancellationException, que no es un error sino la
     * señal de que el usuario cambió de búsqueda.
     *
     * En React sería un `try { ... } catch { return [] }` dentro de
     * un `Promise.allSettled`.
     *
     * Recibe lat/lng para que los DESTACADOS entren en el mismo
     * círculo de 5 km que los normales (R1.2): si no, un destacado
     * a 12 km aparecería sobre resultados que se cortaron en 5.
     */
    private suspend fun fetchFeaturedFor(
        text: String?,
        category: Int?,
        lat: Double?,
        lng: Double?,
    ): List<Business> =
        try {
            val featured = ApiClient.api.getFeaturedBySearch(
                text = text,
                category = category,
                lat = lat,
                lng = lng,
                radius = if (lat != null && lng != null) HomeUiState.RADIO_KM.toDouble() else null,
            )
            Log.d(TAG, "featured-by-search → ${featured.size} resultados")
            featured
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "featured-by-search falló: ${e::class.simpleName}: ${e.message}")
            emptyList()
        }

    /**
     * GET /api/categories/ — los chips son "nice to have": si fallan,
     * la pantalla sigue siendo útil, así que NO disparamos el error
     * hacia la UI como si fuera un error de búsqueda.
     *
     * SÍ lo marcamos en `categoriesError` para que la pantalla pueda
     * avisarlo con un snackbar (antes los chips desaparecían en
     * silencio y nadie sabía por qué).
     *
     * ⚠️ AUNDO ASÍ lo registramos con Log. Tragar la excepción a
     * ciegas escondió un fallo real y los chips desaparecieron sin
     * que nadie supiera por qué.
     */
    private fun loadCategories() {
        viewModelScope.launch {
            // Al reintentar hay que bajar la bandera: si no, la clave
            // del LaunchedEffect no cambia y el snackbar no se repetiría.
            _uiState.update { it.copy(categoriesError = false) }

            try {
                val response = ApiClient.api.getCategories(pageSize = 50)
                _uiState.update { it.copy(categories = response.results) }
                Log.d(TAG, "Categorías OK → ${response.results.size}")
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Fallo categorías: ${e::class.simpleName}: ${e.message}", e)
                _uiState.update { it.copy(categoriesError = true) }
            }
        }
    }

    private companion object {
        const val TAG = "HomeViewModel"
    }
}
