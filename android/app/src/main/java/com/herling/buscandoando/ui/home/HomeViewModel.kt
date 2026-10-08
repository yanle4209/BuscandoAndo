package com.herling.buscandoando.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import android.util.Log
import com.herling.buscandoando.core.data.MunicipioStore
import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.data.dto.Cabecera
import com.herling.buscandoando.core.data.dto.Category
import com.herling.buscandoando.core.data.dto.CorrectionPayload
import com.herling.buscandoando.core.network.ApiClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.Response

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
 * ── La máquina de estados de la web ────────────────────────────────
 *
 * Las transiciones de `modo` / `punto` / `destino` / `llego` viven en
 * [HomeMachine] (el `reducer` de Home.jsx). Aquí solo se orquesta: se
 * aplica la transición, se miran los efectos que en React son
 * `useEffect` (refresco por movimiento, reset R3.2, borrado sin punto)
 * y se dispara la consulta.
 *
 * `viewModelScope` es una corrutina ligada al ciclo de vida del
 * ViewModel: si el usuario sale de la pantalla, las peticiones en
 * vuelo se cancelan SOLEAS (no quedan zombis).
 */
class HomeViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    /** Cancela la búsqueda anterior si se lanza otra (evita respuestas cruzadas). */
    private var searchJob: Job? = null

    /** Cancela el detalle anterior (se cierra la hoja o se pide otro). */
    private var detailJob: Job? = null

    // ── Refresco automático por movimiento (R1.a) ──
    //
    // Espejo literal de programarRefresco/cancelarRefresco de Home.jsx:
    // el throttle NO descarta el punto que llega dentro de la ventana,
    // lo deja pendiente y dispara al vencer. Si no, quien camina y se
    // detiene justo en esa ventana se quedaría mirando resultados viejos.
    private var refrescoJob: Job? = null
    private var pendienteRefresco: Punto? = null
    private var ultimoRefrescoMs = 0L

    init {
        loadCategories()
        loadCabeceras()
        // OJO: aquí NO se consulta nada. Sin punto activo la app se
        // queda en portada, igual que la web (R1.1). El primer resultado
        // sale cuando el usuario busca, elige municipio o pulsa
        // "Mi ubicación".
    }

    // ─────────────── EVENTOS que la UI puede emitir ───────────────

    /**
     * El usuario escribe en la caja. Solo actualiza el texto, NO busca.
     *
     * La Única excepción es vaciarla: espejo del efecto del input de
     * SearchBar.jsx (línea 31), que reintenta la búsqueda al quedar en
     * blanco — y si no queda ningún filtro, vuelve a portada.
     */
    fun onQueryChange(value: String) {
        val antes = _uiState.value
        if (value.isBlank() && antes.haBuscado) {
            aplicarBuscar { it.copy(query = value) }
        } else {
            _uiState.update { it.copy(query = value) }
        }
    }

    /** Enter en el teclado o botón "Buscar". */
    fun onSearch() = aplicarBuscar { it }

    /** Tocó un chip de categoría. Cambia el filtro Y recarga. */
    fun onCategorySelected(category: Category?) = aplicarBuscar {
        it.copy(selectedCategory = category)
    }

    fun onNextPage() {
        val s = _uiState.value
        if (s.canGoNext) aplicar(HomeMachine.pagina(s, s.currentPage + 1), buscar = true)
    }

    fun onPreviousPage() {
        val s = _uiState.value
        if (s.canGoPrevious) aplicar(HomeMachine.pagina(s, s.currentPage - 1), buscar = true)
    }

    /**
     * Botón "Reintentar" del banner de error.
     *
     * ⚠️ También reintenta las CATEGORÍAS y las CABECERAS si no
     * llegaron. De lo contrario, si el servidor estaba dormido al
     * arrancar, los chips quedarían invisibles para siempre.
     */
    fun onRetry() {
        if (_uiState.value.categories.isEmpty()) loadCategories()
        if (_uiState.value.cabeceras.isEmpty()) loadCabeceras()
        if (_uiState.value.haBuscado) search(page = _uiState.value.currentPage)
    }

    // ─────────────── Municipio (R3.4) ───────────────

    /**
     * El usuario eligió (o quitó) un municipio en el selector.
     *
     * Elegir EMPIEZA a consultar y además se RECUERDA entre sesiones
     * (R3.4); quitar borra ese recuerdo. El punto del mapa, en cambio,
     * no se guarda nunca.
     */
    fun onMunicipioSelected(cabecera: Cabecera?) {
        if (cabecera == null) MunicipioStore.borrar() else MunicipioStore.guardar(cabecera)
        val nuevo = HomeMachine.municipio(_uiState.value, cabecera, restaurado = false)
        aplicar(nuevo, buscar = cabecera != null)
    }

    /**
     * El usuario tocó un punto del mapa para buscar desde ahí.
     * Mismo acto que elegir municipio, pero NO se recuerda (R3.4).
     */
    fun onMapPointSelected(lat: Double, lng: Double) {
        val nuevo = HomeMachine.mapa(_uiState.value, Punto(lat, lng))
        aplicar(nuevo, buscar = true)
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

    // ───────────── Fase 9-B · botón "Corregir" ─────────────

    /**
     * Tocó "Corregir" en la tarjeta: abre el formulario.
     *
     * Espejo de `setCorrectionBiz(biz)` de Home.jsx. Todavía no se pide
     * nada al backend: el modal solo recuerda QUÉ negocio se quiere
     * corregir (`correccionId != null` = modal abierto).
     */
    fun onOpenCorrection(business: Business) {
        _uiState.update {
            it.copy(
                correccionId = business.id,
                correccionNombre = business.name,
                correccionEnviando = false,
                correccionEnviada = false,
                correccionError = null,
            )
        }
    }

    /**
     * Cerró el modal (X, tap afuera o "Entendido"): se borra todo.
     *
     * Mientras el POST está en vuelo NO se cierra: si no, el usuario
     * podría reenviar sin darse cuenta y el backend recibiría dos
     * avisos iguales.
     */
    fun onCloseCorrection() {
        if (_uiState.value.correccionEnviando) return
        _uiState.update {
            it.copy(
                correccionId = null,
                correccionNombre = "",
                correccionEnviando = false,
                correccionEnviada = false,
                correccionError = null,
            )
        }
    }

    /**
     * Envió el formulario → POST /api/corrections/ (público, sin login).
     *
     * La composable ya validó los 10 caracteres que exige
     * `validate_mensaje` (y lo cuenta en pantalla); aquí solo se manda.
     *
     * `correccionError` guarda el motivo del backend cuando lo trae
     * (DRF responde {"mensaje": ["…"]}), y "" cuando no lo hay: en ese
     * caso el modal pinta el mensaje genérico de strings.xml.
     */
    fun onSendCorrection(campo: String, mensaje: String) {
        val negocio = _uiState.value.correccionId ?: return
        val texto = mensaje.trim()
        if (texto.isEmpty()) return
        if (_uiState.value.correccionEnviando) return

        _uiState.update { it.copy(correccionEnviando = true, correccionError = null) }

        viewModelScope.launch {
            try {
                val respuesta = ApiClient.api.createCorrection(
                    CorrectionPayload(business = negocio, campo = campo, mensaje = texto),
                )
                Log.d(TAG, "corrections → HTTP ${respuesta.code()}")

                if (respuesta.isSuccessful) {
                    _uiState.update { it.copy(correccionEnviando = false, correccionEnviada = true) }
                } else {
                    _uiState.update {
                        it.copy(
                            correccionEnviando = false,
                            correccionError = detalleDeError(respuesta) ?: "",
                        )
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Sin internet, servidor dormido, timeout...
                Log.w(TAG, "corrections falló: ${e::class.simpleName}: ${e.message}")
                _uiState.update { it.copy(correccionEnviando = false, correccionError = "") }
            }
        }
    }

    /**
     * Saca el primer mensaje legible del 4xx de DRF.
     *
     * DRF responde JSON con forma {"campo": ["Dato invalido"]} y el
     * backend añade "Cuentanos un poco mas: al menos 10 caracteres."
     * para `mensaje`. En vez de enseñar JSON crudo al usuario,
     * buscamos el primer texto de los campos que conocemos.
     */
    private fun detalleDeError(respuesta: Response<*>): String? {
        val cuerpo = try {
            respuesta.errorBody()?.string()
        } catch (e: Exception) {
            null
        } ?: return null

        return try {
            val objeto = Json.parseToJsonElement(cuerpo).jsonObject
            listOf("mensaje", "campo", "business", "non_field_errors")
                .firstNotNullOfOrNull { clave ->
                    (objeto[clave] as? JsonArray)?.firstOrNull()?.jsonPrimitive?.contentOrNull
                }
        } catch (e: Exception) {
            // Un cuerpo que no es JSON (p. ej. el HTML del 500 de
            // Render): mejor nada que HTML en la pantalla.
            null
        }
    }

    // ───────────── Fase 8 · GPS y máquina de estados ─────────────

    /**
     * Vamos a buscar el fix: solo marcamos "buscando".
     *
     * El PERMISO lo pide la UI (necesita un diálogo del sistema y una
     * explicación) y las coordenadas las obtiene la UI y nos las
     * devuelve con [onGpsFix] o [onGpsForzado].
     */
    fun onStartLocating() {
        _uiState.update { it.copy(locationStatus = LocationStatus.Locating) }
    }

    /**
     * Fix del WATCH (posición en movimiento). Espejo de
     * `dispatch({ type: 'gps', pos })` de Home.jsx.
     *
     * Encadena los tres efectos del `useEffect` de posiciones:
     *  1. reset R3.2 si te alejas de un destino ya alcanzado,
     *  2. refresco por movimiento con throttle de 30 s,
     *  3. nueva consulta si el punto de consulta cambió de modo.
     */
    fun onGpsFix(lat: Double, lng: Double) {
        val antes = _uiState.value
        val pos = Punto(lat, lng)
        val nuevo = HomeMachine.gps(antes, pos)
        _uiState.update { nuevo.copy(locationStatus = LocationStatus.Active) }

        // R3.2: salir de >5 km del destino DESPUÉS de haber entrado
        // borra TODO y vuelve a portada.
        if (HomeMachine.necesitaReset(nuevo, pos)) {
            cancelarRefresco()
            aplicar(HomeMachine.reset(nuevo), buscar = false)
            return
        }

        val puntoCambio = nuevo.punto != antes.punto
        if (puntoCambio) {
            // S0→S1 o S2→S1: cambió el centro del círculo consultado.
            // Con una búsqueda encima hay que pedirla otra vez; sin ella
            // (portada) se queda como está, igual que en la web.
            if (nuevo.haBuscado) search(page = 1)
        } else if (HomeMachine.refrescoPorMovimiento(nuevo, pos)) {
            // R1.a: te has alejado ≥ 500 m del último punto consultado.
            programarRefresco(pos)
        }
    }

    /**
     * Botón "Mi ubicación": es EXPLÍCITO, además de mover el punto
     * EMPIEZA a consultar (forzar_gps de Home.jsx 167-201).
     */
    fun onGpsForzado(lat: Double, lng: Double) {
        val nuevo = HomeMachine.forzarGps(_uiState.value, Punto(lat, lng))
        _uiState.update { nuevo.copy(locationStatus = LocationStatus.Active) }
        aplicar(nuevo, buscar = true)
    }

    /**
     * No hubo permiso, no hubo GPS o se agotó el tiempo de espera.
     *
     * Espejo del error de `getCurrentPosition` (Home.jsx 313): se
     * restaura el municipio GUARDADO, que es la única salida que tiene
     * quien no puede usar GPS (R1.1). Si lo había, el usuario ni se
     * entera: los resultados salen solos. Si no lo había, queda la
     * portada con el aviso.
     */
    fun onLocationFailed() {
        val actual = _uiState.value

        // Un fix posterior hace inútil este aviso: no tapamos lo bueno.
        if (actual.locationStatus == LocationStatus.Active) return

        // Solo restauramos si el usuario no había elegido ya otro destino.
        val guardado = if (actual.destino == null) MunicipioStore.leer() else null

        if (guardado == null) {
            _uiState.update { it.copy(locationStatus = LocationStatus.Denied) }
            return
        }

        val nuevo = HomeMachine.municipio(actual, guardado, restaurado = true)
            .copy(locationStatus = LocationStatus.Idle)
        aplicar(nuevo, buscar = true)
    }

    /** 15 s sin fix: mismo camino que un fallo de permiso. */
    fun onGpsTimeout() {
        if (_uiState.value.locationStatus == LocationStatus.Locating) onLocationFailed()
    }

    /**
     * La X de "Cerca de mí": quitar la ubicación es volver a empezar.
     * Aplica el mismo `reset` total que R3.2 (borra filtros y destino).
     */
    fun onClearLocation() {
        cancelarRefresco()
        aplicar(HomeMachine.reset(_uiState.value), buscar = false)
    }

    // ─────────────── Acceso a datos ───────────────

    /**
     * GET /api/businesses/?page=&page_size=12&text=&category=&lat=&lng=&radius=
     *
     * R1.1: sin punto activo NO se consulta nada y los resultados que
     * hubiera se borran (efecto de Home.jsx línea 440).
     *
     * `ifBlank { null }` es clave: Retrofit NO agrega los parámetros
     * cuyo valor es null, así que una búsqueda vacía manda
     * /api/businesses/?page=1&page_size=12&lat=…  (sin &text=)
     */
    private fun search(page: Int) {
        searchJob?.cancel()

        val punto = _uiState.value.punto
        if (punto == null) {
            limpiarResultados()
            return
        }

        searchJob = viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }

            try {
                val current = _uiState.value
                val text = current.query.trim().ifBlank { null }
                val catId = current.selectedCategory?.id

                // Deja en logcat QUÉ mandamos al API (punto + filtros).
                Log.d(
                    "BuscandoAndo",
                    "search page=$page text='${current.query}' cat=$catId " +
                        "lat=${punto.lat} lng=${punto.lng} radio=${HomeUiState.RADIO_KM}km " +
                        "modo=${current.mode}",
                )

                // ── Los DESTACADOS viajan EN PARALELO ──
                //
                // `async` lanza la corrutina YA mismo (es "eager"), así
                // que mientras `getBusinesses` se queda esperando a la
                // red, este otro trabajo corre solo. Es el equivalente a:
                //
                //   const [res, feat] = await Promise.all([fetch(..), fetch(..)])
                //
                // Si no hay filtros el endpoint devuelve [] por contrato,
                // así que ni lo pedimos.
                val featuredJob = if (text == null && catId == null) {
                    null
                } else {
                    async { fetchFeaturedFor(text, catId, punto) }
                }

                val response = ApiClient.api.getBusinesses(
                    page = page,
                    pageSize = HomeUiState.PAGE_SIZE,
                    text = text,
                    category = catId,
                    // ── El círculo de 5 km ──
                    // El punto SIEMPRE existe aquí (si no, ya habríamos
                    // salido arriba), así que lat/lng/radius van juntos:
                    // nadie consulta "a todo el país" (R3.5).
                    lat = punto.lat,
                    lng = punto.lng,
                    radius = HomeUiState.RADIO_KM.toDouble(),
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
     * GET /api/businesses/featured-by-search/
     *
     * Es una llamada SECUNDARIA: si falla, la búsqueda principal NO
     * debe caer. Por eso esta función JAMÁS lanza hacia arriba —
     * devuelve una lista (vacía si algo malo pasa) y solo vuelve a
     * lanzar la CancellationException, que no es un error sino la
     * señal de que el usuario cambió de búsqueda.
     *
     * Recibe el punto para que los DESTACADOS entren en el MISMO
     * círculo de 5 km que los normales (R1.2): si no, un destacado
     * a 12 km aparecería sobre resultados que se cortaron en 5.
     */
    private suspend fun fetchFeaturedFor(
        text: String?,
        category: Int?,
        punto: Punto,
    ): List<Business> =
        try {
            val featured = ApiClient.api.getFeaturedBySearch(
                text = text,
                category = category,
                lat = punto.lat,
                lng = punto.lng,
                radius = HomeUiState.RADIO_KM.toDouble(),
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
     * GET /api/cabeceras/ — las 158 cabeceras municipales.
     *
     * Sin ellas el selector de municipio no existe, y el municipio es
     * la ÚNICA salida que tiene quien niega la ubicación (R1.1). Por
     * eso se piden ya al arrancar, igual que en Home.jsx línea 278.
     */
    private fun loadCabeceras() {
        viewModelScope.launch {
            _uiState.update { it.copy(cabecerasError = false) }
            try {
                val cabeceras = ApiClient.api.getCabeceras()
                _uiState.update { it.copy(cabeceras = cabeceras) }
                Log.d(TAG, "cabeceras → ${cabeceras.size}")
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Fallo cabeceras: ${e::class.simpleName}: ${e.message}", e)
                _uiState.update { it.copy(cabecerasError = true) }
            }
        }
    }

    /**
     * GET /api/categories/ — los chips son "nice to have": si fallan,
     * la pantalla sigue siendo útil, así que NO disparamos el error
     * hacia la UI como si fuera un error de búsqueda.
     *
     * SÍ lo marcamos en `categoriesError` para que la pantalla pueda
     * avisarlo con un snackbar (antes los chips desaparecían en
     * silencio y nadie sabía por qué).
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

    // ─────────────── orquestación ───────────────

    /**
     * Aplica un filtro (texto o categoría) y decide si hay consulta.
     *
     * Espejo de `case 'buscar'`: se conserva lo demás, se vuelve a la
     * página 1 y un filtro vacío vuelve a la portada SIN borrar lo que
     * ya se cargó.
     */
    private fun aplicarBuscar(transform: (HomeUiState) -> HomeUiState) {
        val nuevo = HomeMachine.buscar(transform(_uiState.value))
        aplicar(nuevo, buscar = nuevo.haBuscado)
    }

    /**
     * Pinta un estado nuevo y deja la búsqueda al día.
     *
     *   - sin punto  → se borran los resultados (efecto Home.jsx 440)
     *   - con punto  → se pide la página que toca (efecto 430-432)
     */
    private fun aplicar(nuevo: HomeUiState, buscar: Boolean) {
        _uiState.update { nuevo }
        when {
            nuevo.punto == null -> limpiarResultados()
            buscar && nuevo.haBuscado -> search(page = nuevo.currentPage)
        }
    }

    /**
     * Borra resultados, destacados y totales.
     *
     * `hasLoaded = true` significa "ya sabemos que aquí no hay nada",
     * para que la UI pinte el vacío en vez de un grid fantasma.
     */
    private fun limpiarResultados() {
        _uiState.update {
            it.copy(
                businesses = emptyList(),
                featuredBySearch = emptyList(),
                totalCount = 0,
                currentPage = 1,
                hasLoaded = true,
                isLoading = false,
                errorMessage = null,
            )
        }
    }

    /**
     * Refresco automático por movimiento (R1.a) con throttle de 30 s.
     *
     * Si el disparo cae dentro de la ventana NO se descarta: se deja el
     * último punto pendiente y se dispara al vencer.
     */
    private fun programarRefresco(pos: Punto) {
        pendienteRefresco = pos

        val espera = HomeUiState.THROTTLE_MS - (System.currentTimeMillis() - ultimoRefrescoMs)
        if (espera <= 0) {
            refrescar()
            return
        }
        if (refrescoJob?.isActive == true) return

        refrescoJob = viewModelScope.launch {
            delay(espera)
            refrescar()
        }
    }

    private fun refrescar() {
        val pos = pendienteRefresco ?: return
        pendienteRefresco = null
        ultimoRefrescoMs = System.currentTimeMillis()

        val antes = _uiState.value
        val nuevo = HomeMachine.mover(antes, pos)
        if (nuevo.punto == antes.punto) return   // no llegó al umbral

        _uiState.update { nuevo }
        if (nuevo.haBuscado) search(page = 1)
    }

    private fun cancelarRefresco() {
        refrescoJob?.cancel()
        refrescoJob = null
        pendienteRefresco = null
    }

    override fun onCleared() {
        cancelarRefresco()
        super.onCleared()
    }

    private companion object {
        const val TAG = "HomeViewModel"
    }
}
