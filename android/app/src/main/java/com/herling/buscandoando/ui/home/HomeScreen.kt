package com.herling.buscandoando.ui.home

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.LocationSearching
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil3.compose.AsyncImage
import com.herling.buscandoando.R
import com.herling.buscandoando.core.data.FeaturedTier
import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.data.dto.Cabecera
import com.herling.buscandoando.core.location.getCurrentCoordinates
import com.herling.buscandoando.core.location.hasLocationPermission
import com.herling.buscandoando.core.location.locationUpdates
import com.herling.buscandoando.ui.iconForCategory
import com.herling.buscandoando.ui.theme.CanaryYellow
import com.herling.buscandoando.ui.theme.CanvasWhite
import com.herling.buscandoando.ui.theme.BrandBrown
import com.herling.buscandoando.ui.theme.CardWhite
import com.herling.buscandoando.ui.theme.SurfaceWhite
import com.herling.buscandoando.ui.theme.Hairline
import com.herling.buscandoando.ui.theme.HairlineStrong
import com.herling.buscandoando.ui.theme.Gold
import com.herling.buscandoando.ui.theme.GoldInk
import com.herling.buscandoando.ui.theme.GreyOlive
import com.herling.buscandoando.ui.theme.StatusBySchedule
import com.herling.buscandoando.ui.theme.StatusClosed
import com.herling.buscandoando.ui.theme.StatusOpen
import com.herling.buscandoando.ui.theme.TextMuted
import com.herling.buscandoando.ui.theme.TextOnYellow
import com.herling.buscandoando.ui.theme.TextPrimary
import com.herling.buscandoando.ui.theme.TextSecondary
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.Collator
import java.text.Normalizer
import java.util.Locale

/** Etiqueta para logcat (Fase 6: seguir el GPS desde Android Studio). */
private const val TAG = "BuscandoAndo"

/**
 * Los DOS permisos de ubicación que se piden juntos (Android 12+ deja
 * elegir solo el aproximado).
 */
private val LOCATION_PERMISSIONS = arrayOf(
    Manifest.permission.ACCESS_FINE_LOCATION,
    Manifest.permission.ACCESS_COARSE_LOCATION,
)

/** Sin fix en 15 s → se restaura el municipio guardado (timeout de la web). */
private const val GPS_TIMEOUT_MS = 15_000L

/**
 * Pantalla Home: búsqueda → chips de categoría → cuadrícula de
 * tarjetas → paginación.
 *
 * Estructura (unidirectional data flow):
 *
 *   HomeScreen  ──lee──>  uiState: StateFlow<HomeUiState>
 *      │                        ▲
 *      └──emite eventos─────────┘  HomeViewModel
 *
 * La composable NO sabe qué es Retrofit: solo pinta el estado y
 * reporta lo que el usuario hace.
 */
@Composable
fun HomeScreen(
    viewModel: HomeViewModel = viewModel(),
    onOpenMap: () -> Unit,
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // ═══════════ FASE 8 · permiso, watch y portada ═══════════
    //
    // La composable es la ÚNICA que habla con el sistema operativo
    // (diálogo de permisos, GPS). El ViewModel solo sabe de estados.
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // El watch (geo.watchPosition de la web) vive mientras está esta
    // pantalla: al salir se cancela solo, porque va con el scope de
    // rememberCoroutineScope — sin eso el GPS seguiría corriendo con
    // la pantalla cerrada.
    var watchJob by remember { mutableStateOf<Job?>(null) }

    // Si el permiso se pidió desde el botón "Mi ubicación", el fix que
    // llegue tiene que ser EXPLÍCITO (forzar_gps); si fue al abrir, no.
    var gpsExplicitoPendiente by remember { mutableStateOf(false) }

    /**
     * Arranca el GPS: fix rápido de vuelo + watch de posiciones.
     *
     * Espejo del useEffect de GPS de Home.jsx (304-322):
     * `getCurrentPosition` para tener coordenadas YA y `watchPosition`
     * para seguir moviéndote (refresco R1.a).
     */
    fun arrancarGps(explicito: Boolean) {
        viewModel.onStartLocating()

        if (watchJob == null) {
            watchJob = scope.launch {
                runCatching {
                    context.locationUpdates().collect { loc ->
                        viewModel.onGpsFix(loc.latitude, loc.longitude)
                    }
                }.onFailure { Log.w(TAG, "watch de ubicación parado: ${it.message}") }
            }

            // 15 s sin fix = mismo camino que un fallo de permiso: se
            // restaura el municipio guardado y no se queda colgada la
            // barra "Buscando tu ubicación…" para siempre.
            scope.launch {
                delay(GPS_TIMEOUT_MS)
                viewModel.onGpsTimeout()
            }
        }

        scope.launch {
            val fix = context.getCurrentCoordinates()
            Log.d(TAG, "fix = ${fix?.latitude}, ${fix?.longitude}")
            if (fix == null) return@launch
            if (explicito) viewModel.onGpsForzado(fix.latitude, fix.longitude)
            else viewModel.onGpsFix(fix.latitude, fix.longitude)
        }
    }

    /**
     * Diálogo del sistema de Android: "¿Permitir a BuscandoAndo usar
     * la ubicación del dispositivo?".
     *
     * Se piden las DOS variantes (fina y aproximada): en Android 12+
     * el usuario puede elegir solo "Aproximada", y con un radio de
     * 5 km eso es de sobra. Si solo miráramos FINE, daríamos por
     * denegado un permiso concedido.
     */
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions(),
    ) { resultados ->
        if (resultados.values.any { it }) {
            arrancarGps(explicito = gpsExplicitoPendiente)
        } else {
            // "No volver a preguntar" → Android responde al instante y
            // caemos en Denied (por eso ese estado ofrece "Ajustes").
            viewModel.onLocationFailed()
        }
    }

    fun requestLocation() {
        if (context.hasLocationPermission()) {
            arrancarGps(explicito = true)
        } else {
            gpsExplicitoPendiente = true
            permissionLauncher.launch(LOCATION_PERMISSIONS)
        }
    }

    /**
     * R3.6 · "Mi ubicación manda al abrir": el permiso se pide SOLO,
     * igual que hace la web al cargar (getCurrentPosition en el
     * mount). Si el usuario lo niega, no se vuelve a insistir en cada
     * arranque: Android lo hace solo a partir de la segunda vez.
     */
    LaunchedEffect(Unit) {
        if (context.hasLocationPermission()) {
            arrancarGps(explicito = false)
        } else {
            gpsExplicitoPendiente = false
            permissionLauncher.launch(LOCATION_PERMISSIONS)
        }
    }

    /** Abre la ficha de la app en Ajustes (salida para permiso bloqueado). */
    fun openAppSettings() {
        val intent = Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.fromParts("package", context.packageName, null),
        )
        runCatching { context.startActivity(intent) }
    }
    // ══════════════════════════════════════════════

    HomeContent(
        state = state,
        onQueryChange = viewModel::onQueryChange,
        onSearch = viewModel::onSearch,
        onCategorySelected = viewModel::onCategorySelected,
        onMunicipioSelected = viewModel::onMunicipioSelected,
        onPreviousPage = viewModel::onPreviousPage,
        onNextPage = viewModel::onNextPage,
        onRetry = viewModel::onRetry,
        onOpenMap = onOpenMap,
        onMyLocation = { requestLocation() },
        onClearLocation = viewModel::onClearLocation,
        onOpenSettings = { openAppSettings() },
        onBusinessClick = { business ->
            // slug viene como String? — si no trae, no hacemos nada
            business.slug?.let(viewModel::onBusinessSelected)
        },
    )

    // ── FASE 4: hoja modal con el detalle ──
    // Se compone SOLO cuando hay slug seleccionado. Es el equivalente
    // exacto de  {slug && <Modal/>}  en React.
    if (state.detailSlug != null) {
        BusinessDetailSheet(
            state = state,
            onDismiss = viewModel::onCloseDetail,
            onRetry = viewModel::onRetryDetail,
        )
    }
}

@Composable
private fun HomeContent(
    state: HomeUiState,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit,
    onCategorySelected: (com.herling.buscandoando.core.data.dto.Category?) -> Unit,
    onMunicipioSelected: (Cabecera?) -> Unit,
    onPreviousPage: () -> Unit,
    onNextPage: () -> Unit,
    onRetry: () -> Unit,
    onOpenMap: () -> Unit,
    onMyLocation: () -> Unit,
    onClearLocation: () -> Unit,
    onOpenSettings: () -> Unit,
    onBusinessClick: (Business) -> Unit,
) {
    // ── Fase 7 · avisos TRANSIATORIOS ──
    //
    // Un snackbar es para lo que "se va solo": aquí lo usamos para el
    // fallo de CATEGORÍAS y de CABECERAS, que si no desaparecerían en
    // silencio (ambos son "nice to have" y su error se traga a propósito).
    //
    // NO lo usamos para el fallo de BÚSQUEDA: ahí ya hay un banner
    // fijo con botón "Reintentar", que es mejor porque no caduca.
    val snackbarHostState = remember { SnackbarHostState() }
    val categoriesErrorMessage = stringResource(R.string.home_categories_error)
    val cabecerasErrorMessage = stringResource(R.string.home_municipio_error)

    LaunchedEffect(state.categoriesError) {
        if (state.categoriesError) snackbarHostState.showSnackbar(categoriesErrorMessage)
    }

    LaunchedEffect(state.cabecerasError) {
        if (state.cabecerasError) snackbarHostState.showSnackbar(cabecerasErrorMessage)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CanvasWhite)
            // Los insets del sistema: sin esto el título queda DETRÁS
            // del reloj/batería. statusBarsPadding = espacio arriba.
            .statusBarsPadding()
            // Ajusta el contenido cuando sube el teclado (IME)
            .imePadding(),
    ) {
        // ── Cabecera fija: título + buscador + municipio + chips ──
        HomeHeader(
            state = state,
            onQueryChange = onQueryChange,
            onSearch = onSearch,
            onCategorySelected = onCategorySelected,
            onMunicipioSelected = onMunicipioSelected,
            onOpenMap = onOpenMap,
            onMyLocation = onMyLocation,
        )

        // ── Fase 6: estado del GPS (solo dibuja si hay algo que decir) ──
        LocationBar(
            state = state,
            onRetry = onMyLocation,
            onClear = onClearLocation,
            onOpenSettings = onOpenSettings,
        )

        // ── Filete de cabecera: 3px de amarillo, igual que el
        //    #header de la web. Separa sobre fondo blanco ──
        HorizontalDivider(color = CanaryYellow, thickness = 3.dp)

        // ── Contador de resultados (espejo de .right-section-header) ──
        // Solo EXISTE tras la primera consulta: en portada no hay nada
        // que contar.
        if (state.haBuscado) {
            ResultsHeader(state = state)
        }

        // ── Cuerpo ──
        // R1.1: sin la primera consulta, la PORTADA ocupa el hueco de la
        // rejilla (`.right-portada` de Home.jsx), con el aviso de cómo
        // salir de ahí cuando todavía no hay punto activo.
        when {
            !state.haBuscado -> PortadaOverlay(
                modifier = Modifier.weight(1f),
                hint = portadaHint(state),
            )

            state.isLoading && state.businesses.isEmpty() ->
                CenteredMessage(Modifier.weight(1f)) {
                    CircularProgressIndicator(color = GoldInk, strokeWidth = 3.dp)
                    Spacer(Modifier.height(14.dp))
                    Text(
                        text = stringResource(R.string.home_loading),
                        color = TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }

            state.errorMessage != null && state.businesses.isEmpty() ->
                ErrorState(
                    modifier = Modifier.weight(1f),
                    message = state.errorMessage.orEmpty(),
                    onRetry = onRetry,
                )

            state.isEmpty ->
                // 0 destacados + 0 normales -> el MISMO overlay que usa la
                // web en `.sin-resultados` (DISENO.md a1 / m2).
                PortadaOverlay(
                    modifier = Modifier.weight(1f),
                    hint = portadaHint(state),
                )

            else -> {
                // Banner de error no bloqueante (ya hay datos en pantalla)
                val error = state.errorMessage
                if (error != null) {
                    ErrorBanner(message = error, onRetry = onRetry)
                }

                // Fase 7: fila de destacados (solo si hay; ver FeaturedRow)
                FeaturedRow(
                    featured = state.featuredBySearch,
                    onBusinessClick = onBusinessClick,
                )

                BusinessGrid(
                    state = state,
                    modifier = Modifier.weight(1f),
                    onBusinessClick = onBusinessClick,
                )
            }
        }

        // ── Paginación (mismo guardante que la web: hay varias páginas,
        //    no está cargando y no estamos en el overlay vacío) ──
        if (state.haBuscado && !state.isLoading && state.totalPages > 1 &&
            state.businesses.isNotEmpty()
        ) {
            PaginationBar(
                state = state,
                onPreviousPage = onPreviousPage,
                onNextPage = onNextPage,
            )
        }

        // El snackbar va el ÚLTIMO: cuando aparece le roba alto al
        // cuerpo (que tiene weight(1f)) en vez de tapar la cuadrícula.
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 14.dp),
        )
    }
}

// ═══════════════════════ CABECERA ═══════════════════════

@Composable
private fun HomeHeader(
    state: HomeUiState,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit,
    onCategorySelected: (com.herling.buscandoando.core.data.dto.Category?) -> Unit,
    onMunicipioSelected: (Cabecera?) -> Unit,
    onOpenMap: () -> Unit,
    onMyLocation: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(14.dp))

        // Título + botones (ubicación · mapa) en la misma línea.
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = "BuscandoAndo",
                    // Título marrón como .right-brand-title de la web
                    color = BrandBrown,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Black,
                )
                // El subtítulo dice el ALCANCE de la búsqueda, no un sitio
                // fijo: al elegir municipio cambia solo (el hardcodeo
                // "Moca · Espaillat" mentía en cuanto te ibas del municipio).
                Text(
                    text = when {
                        state.destino == null -> stringResource(R.string.home_subtitle_country)
                        state.municipioEtiqueta != null -> state.municipioEtiqueta.orEmpty()
                        else -> stringResource(R.string.home_subtitle_map_point)
                    },
                    color = TextMuted,
                    style = MaterialTheme.typography.labelMedium,
                )
            }

            // ── Fase 6: ubicación ──
            // Icono AMARILLO cuando el filtro por cercanía está activo
            // (misma regla que los chips: amarillo = "está aplicado").
            IconButton(onClick = onMyLocation) {
                if (state.locationStatus == LocationStatus.Locating) {
                    CircularProgressIndicator(
                        color = GoldInk,
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(20.dp),
                    )
                } else {
                    Icon(
                        imageVector = if (state.hasLocation) {
                            Icons.Default.MyLocation
                        } else {
                            Icons.Default.LocationSearching
                        },
                        contentDescription = stringResource(R.string.home_my_location),
                        tint = if (state.mode == SearchMode.Gps) GoldInk else TextSecondary,
                    )
                }
            }

            IconButton(onClick = onOpenMap) {
                Icon(
                    imageVector = Icons.Default.Map,
                    contentDescription = stringResource(R.string.home_open_map),
                    tint = GoldInk,
                )
            }
        }

        Spacer(Modifier.height(12.dp))

        SearchField(
            query = state.query,
            onQueryChange = onQueryChange,
            onSearch = onSearch,
        )

        Spacer(Modifier.height(12.dp))

        // R1.1: sin GPS, elegir municipio es OBLIGATORIO, así que el
        // selector va FUERA de cualquier panel y a la vista (lo mismo
        // que en la web, donde nunca está escondido tras "Filtros").
        MunicipioSelector(
            clave = state.municipioClave,
            cabeceras = state.cabeceras,
            onSelect = onMunicipioSelected,
        )

        Spacer(Modifier.height(12.dp))

        CategoryChips(
            categories = state.categories,
            selected = state.selectedCategory,
            onSelect = onCategorySelected,
        )

        Spacer(Modifier.height(14.dp))
    }
}

// ═══════════════════════ UBICACIÓN (Fase 6) ═══════════════════════

/**
 * Barra de estado del GPS. Vive justo DEBAJO de la cabecera y se
 * dibuja SOLO si hay algo que decir: `Idle` no ocupa ni 1dp, así que
 * no deja huecos cuando el usuario nunca tocó el botón.
 *
 * Un único `when` exhaustivo para los tres casos:
 *
 *   Locating → "esperando el fix"      (spinner)
 *   Active   → "cerca de mí" + radio fijo de 5 km + botón de quitar
 *   Denied   → explicación + Reintentar + Ajustes
 *
 * El compilador de Kotlin garantiza que, si mañana añades un valor al
 * enum, este `when` deje de compilar hasta que lo atiendas.
 */
@Composable
private fun LocationBar(
    state: HomeUiState,
    onRetry: () -> Unit,
    onClear: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    if (state.locationStatus == LocationStatus.Idle) return

    // Cuando manda un municipio o un punto del mapa, el punto de
    // consulta ERES tú solo cuando el modo es GPS: en ese caso la barra
    // "cerca de mí" confundiría (estás buscando en otro sitio).
    if (state.locationStatus == LocationStatus.Active && state.mode != SearchMode.Gps) return

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp)) {
        when (state.locationStatus) {
            LocationStatus.Idle -> Unit   // ya salimos arriba

            LocationStatus.Locating -> Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(top = 2.dp, bottom = 12.dp),
            ) {
                CircularProgressIndicator(
                    color = GoldInk,
                    strokeWidth = 2.dp,
                    modifier = Modifier.size(14.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.home_locating),
                    color = TextSecondary,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            LocationStatus.Active -> {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Place,
                        contentDescription = null,
                        tint = GoldInk,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = stringResource(R.string.home_near_me),
                        color = GoldInk,
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    // ACCESIBILIDAD: aquí había `modifier = size(32.dp)` y
                    // eso ANULABA los 48dp mínimos de toque que IconButton
                    // trae de fábrica. El icono ya es de 16dp por dentro,
                    // así que solo quitamos el atajo de tamaño.
                    IconButton(onClick = onClear) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = stringResource(R.string.home_location_clear),
                            tint = TextSecondary,
                            modifier = Modifier.size(16.dp),
                        )
                    }
                }

                // El radio es FIJO (R1.3): sin chips que elegir. Aquí
                // solo se dice en qué circulo se está buscando, para
                // que "Cerca de mí" no suene a sin límite.
                Text(
                    text = stringResource(R.string.home_radius_fixed, HomeUiState.RADIO_KM),
                    color = TextSecondary,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 2.dp, bottom = 12.dp),
                )
            }

            LocationStatus.Denied -> {
                Row(verticalAlignment = Alignment.Top) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = null,
                        tint = StatusClosed,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            text = stringResource(R.string.home_location_denied),
                            color = TextPrimary,
                            style = MaterialTheme.typography.labelLarge,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            text = stringResource(R.string.home_location_denied_hint),
                            color = TextMuted,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }

                // Dos salidas: reintentar (vuelve a mostrar el diálogo
                // del sistema) y Ajustes (si Android ya no deja volver
                // a preguntar, allí el usuario lo activa a mano).
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 2.dp, bottom = 8.dp),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(onClick = onRetry) {
                        Text(
                            text = stringResource(R.string.home_error_retry),
                            color = GoldInk,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    TextButton(onClick = onOpenSettings) {
                        Text(
                            text = stringResource(R.string.home_open_settings),
                            color = GoldInk,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            }
        }
    }
}

/**
 * Caja de búsqueda con:
 *  - "glow" amarillo animado cuando tiene el foco
 *  - acción de teclado = buscar (sin necesidad de botón)
 *
 * NOTA: NO tiene autofoco. En la web el `autoFocus` abre el teclado
 * y tapa la mitad de la pantalla; aquí el usuario toca la caja
 * cuando quiere escribir.
 */
@Composable
private fun SearchField(
    query: String,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    val focusManager = LocalFocusManager.current

    // Radio del buscador: --radius-sm de la web (8px)
    val shape = RoundedCornerShape(8.dp)

    // Glow: animamos elevación (la sombra) y el color del borde.
    // La web usa un halo ajustado: box-shadow 0 0 0 3px amarillo.
    val elevation by animateDpAsState(
        targetValue = if (focused) 6.dp else 0.dp,
        label = "glowElevation",
    )
    val borderColor by animateColorAsState(
        targetValue = if (focused) CanaryYellow else HairlineStrong,
        label = "glowBorder",
    )

    // El contenedor (sombra + fondo + borde) vive FUERA del TextField
    // para que Material3 no pinte su propio contenedor encima.
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(
                elevation = elevation,
                shape = shape,
                ambientColor = CanaryYellow,
                spotColor = CanaryYellow,
            )
            .clip(shape)
            .background(SurfaceWhite)
            .border(1.dp, borderColor, shape),
    ) {
        TextField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier
                .fillMaxWidth()
                .onFocusChanged { focused = it.isFocused },
            placeholder = {
                Text(
                    text = stringResource(R.string.home_search_hint),
                    color = TextMuted,
                )
            },
            singleLine = true,
            leadingIcon = {
                Icon(
                    imageVector = Icons.Default.Search,
                    contentDescription = stringResource(R.string.home_search_label),
                    tint = if (focused) GoldInk else TextSecondary,
                )
            },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    // El botón "Buscar" de la web, en el mismo sitio
                    // (dentro de la caja, a la derecha). El X de borrar
                    // se queda: en móvil no todos saben que se puede
                    // seleccionar y suprimir.
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        TextButton(
                            onClick = {
                                onSearch()
                                focusManager.clearFocus()
                            },
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                        ) {
                            Text(
                                text = stringResource(R.string.home_search_submit),
                                color = GoldInk,
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                            )
                        }

                        IconButton(onClick = { onQueryChange("") }) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                // Sin esto TalkBack anuncia "activar" y nada más.
                                contentDescription = stringResource(R.string.home_search_clear),
                                tint = TextSecondary,
                            )
                        }
                    }
                }
            },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(
                onSearch = {
                    onSearch()
                    focusManager.clearFocus()   // cierra el teclado
                },
            ),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Color.Transparent,
                unfocusedContainerColor = Color.Transparent,
                disabledContainerColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
                disabledIndicatorColor = Color.Transparent,
                cursorColor = GoldInk,
                focusedTextColor = TextPrimary,
                unfocusedTextColor = TextPrimary,
                focusedPlaceholderColor = TextMuted,
                unfocusedPlaceholderColor = TextMuted,
            ),
        )
    }
}

/** Fila horizontal de categorías. "Todas" siempre es la primera. */
@Composable
private fun CategoryChips(
    categories: List<com.herling.buscandoando.core.data.dto.Category>,
    selected: com.herling.buscandoando.core.data.dto.Category?,
    onSelect: (com.herling.buscandoando.core.data.dto.Category?) -> Unit,
) {
    if (categories.isEmpty()) return

    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            CategoryChip(
                text = stringResource(R.string.home_all_categories),
                selected = selected == null,
                onClick = { onSelect(null) },
            )
        }
        items(categories, key = { it.id }) { category ->
            CategoryChip(
                text = category.name,
                selected = selected?.id == category.id,
                onClick = { onSelect(if (selected?.id == category.id) null else category) },
            )
        }
    }
}

@Composable
private fun CategoryChip(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(50)
    Box(
        modifier = Modifier
            .clip(shape)
            .background(if (selected) CanaryYellow else CardWhite)
            .border(1.dp, if (selected) CanaryYellow else HairlineStrong, shape)
            .clickable(onClick = onClick)
            // ACCESIBILIDAD: con 7dp los chips medían ~34dp de alto,
            // por debajo de la zona de toque recomendada. Con 10dp
            // quedan en ~40dp (los chips oficiales de Material3 son
            // de 32dp, o sea bastante más justos todavía).
            .padding(horizontal = 15.dp, vertical = 10.dp),
    ) {
        Text(
            text = text,
            color = if (selected) TextOnYellow else TextSecondary,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            maxLines = 1,
        )
    }
}

// ═══════════════════════ FASE 7 · DESTACADOS ═══════════════════════

/**
 * Destacados de la BÚSQUEDA, en TRES columnas.
 *
 * Espejo de `searchFeatured` en Home.jsx: hasta 3 tarjetas que el
 * endpoint /api/businesses/featured-by-search/ devuelve y que la web
 * pinta POR ENCIMA de los resultados, en `.search-featured-top`
 * (repeat(3, 1fr)) y alineadas con la rejilla que hay debajo.
 *
 * Es contenido de "si hay": si la lista viene vacía (no hay
 * destacados que coincidan, no hay filtros todavía, o la llamada
 * secundaria falló) NO se dibuja NADA — ni un hueco.
 */
@Composable
private fun FeaturedRow(
    featured: List<Business>,
    onBusinessClick: (Business) -> Unit,
) {
    if (featured.isEmpty()) return

    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = stringResource(R.string.home_featured_title),
            color = TextSecondary,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(start = 14.dp, top = 12.dp, end = 14.dp, bottom = 8.dp),
        )

        // Tres columnas alineadas con la rejilla de resultados que hay
        // debajo: mismo margen de 14dp y mismo hueco de 12dp, igual que
        // .search-featured-top en la web (repeat(3, 1fr)). El endpoint
        // devuelve como mucho 3, así que caben las 3 de golpe y no hace
        // falta scroll horizontal.
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            featured.take(3).forEach { business ->
                FeaturedCard(
                    business = business,
                    modifier = Modifier.weight(1f),
                    onClick = { onBusinessClick(business) },
                )
            }
        }
    }
}

/**
 * Tarjeta de la fila de destacados, CON FOTO.
 *
 * Misma portada que BusinessCard —foto a lo ancho, `ContentScale.Crop`
 * y velo marrón encima— pero más baja y sin el punto de estado, para
 * que las 3 quepan en la fila sin robarle alto a la cuadrícula de
 * abajo. El nombre y la categoría van SOBRE la foto, abajo, donde el
 * velo espesa: sobre foto clara el texto del tema no se leía.
 *
 * Sin foto se queda en el fondo de la tarjeta y el texto vuelve a sus
 * colores normales: la fila solo se dibuja cuando la búsqueda ha
 * traído algo, así que no hace falta el placeholder de marca.
 */
@Composable
private fun FeaturedCard(
    business: Business,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val featured = business.is_featured == true ||
        FeaturedTier.levelOf(business.featured_tier) != null
    val imageUrl = business.images.firstOrNull()?.image_url
    val conFoto = !imageUrl.isNullOrBlank()
    // Radio --card (12px) y sombra suave de la web
    val shape = RoundedCornerShape(12.dp)
    // Velo = .biz-card__cover-veil de la web (12% arriba → 62% → 90%)
    val veil = androidx.compose.ui.graphics.Brush.verticalGradient(
        0f to Color(0x1F1C1504),
        0.58f to Color(0x9E1C1504),
        1f to Color(0xE61C1504),
    )

    Box(
        modifier = modifier
            .heightIn(min = 118.dp)
            .shadow(2.dp, shape)
            .clip(shape)
            .background(if (conFoto) BrandBrown else CardWhite)
            // Sin escalonado por nivel y sin filete amarillo: el mismo borde
            // fino para todas, igual que la web.
            .border(1.dp, Hairline, shape)
            .clickable(onClick = onClick),
    ) {
        if (conFoto) {
            AsyncImage(
                model = imageUrl,
                // null a propósito: la tarjeta COMPLETA ya es clicable
                // y el Text de abajo expone el nombre. Si además le
                // pusiéramos contentDescription, TalkBack leería el
                // nombre dos veces.
                contentDescription = null,
                contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )

            // Velo marrón: el nombre se lee sobre cualquier foto
            Box(modifier = Modifier.fillMaxSize().background(veil))
        }

        if (featured) {
            DestacadoBadge(
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(start = 8.dp, top = 8.dp),
            )
        }

        Column(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .fillMaxWidth()
                .padding(horizontal = 9.dp, vertical = 8.dp),
        ) {
            Text(
                text = business.name,
                color = if (conFoto) Color.White else TextPrimary,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )

            Spacer(Modifier.height(4.dp))

            Text(
                text = business.category_name ?: stringResource(R.string.home_no_category),
                color = if (conFoto) CanaryYellow else TextMuted,
                style = MaterialTheme.typography.labelSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

// ═══════════════════════ CUADRÍCULA ═══════════════════════

/**
 * Tarjetas. TRES columnas fijas: las mismas que la rejilla de la web
 * (`.right-results-list { grid-template-columns: repeat(3, …) }`).
 *
 * Antes era `Adaptive(150.dp)`, que en teléfono daba 2 columnas y en
 * tablet 4 — la app no coincidía con la web. Con `Fixed(3)` la página
 * es la misma en los dos sitios: 3 tarjetas por fila, y en tablet el
 * hueco de más se va al ancho de cada tarjeta en vez de a más
 * columnas.
 */
@Composable
private fun BusinessGrid(
    state: HomeUiState,
    modifier: Modifier,
    onBusinessClick: (Business) -> Unit,
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(3),
        modifier = modifier.fillMaxWidth(),
        contentPadding = PaddingValues(14.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(state.businesses, key = { it.id }) { business ->
            BusinessCard(business = business, onClick = { onBusinessClick(business) })
        }
    }
}

@Composable
private fun BusinessCard(
    business: Business,
    onClick: () -> Unit,
) {
    // Destacado: is_featured (o un tier valido heredado) -> pastilla
    // "Destacado". SIN escalonado por nivel: todas las tarjetas miden
    // lo mismo: mismo borde fino para todas, sin filete amarillo.
    val featured = business.is_featured == true ||
        FeaturedTier.levelOf(business.featured_tier) != null
    val shape = RoundedCornerShape(12.dp)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            // Altura MINIMA fija: portada 108 + cuerpo (estado + padding).
            // La foto no puede hacer crecer la tarjeta.
            .heightIn(min = 152.dp)
            // Sombra suave, como .biz-card de la web
            .shadow(2.dp, shape)
            .clip(shape)
            .background(CardWhite)
            .border(1.dp, Hairline, shape)
            .clickable(onClick = onClick),
    ) {
        CardCover(business = business, featured = featured)

        Column(modifier = Modifier.padding(horizontal = 9.dp, vertical = 9.dp)) {
            StatusBadge(business = business)
        }
    }
}

/**
 * Portada de la tarjeta: la foto (o el placeholder de marca si no
 * hay) arriba, con el nombre y la categoría ENCIMA, sobre un velo
 * marrón. Alto fijo y `ContentScale.Crop` = recorte a rellenar, la
 * misma regla que la web (`.biz-card__cover` + object-fit: cover).
 */
@Composable
private fun CardCover(business: Business, featured: Boolean) {
    val imageUrl = business.images.firstOrNull()?.image_url
    val statusColor = statusColorOf(business.effective_status)
    // Velo = mismo degradado que .biz-card__cover-veil de la web
    // (90% abajo → 62% al 42% → 12% arriba). SIN foto la web usa otro,
    // que solo oscurece la banda inferior y deja el blanco arriba.
    val veil = if (imageUrl.isNullOrBlank()) {
        androidx.compose.ui.graphics.Brush.verticalGradient(
            0f to Color.Transparent,
            0.52f to Color.Transparent,
            0.78f to Color(0xE61C1504),
            1f to Color(0xEB1C1504),
        )
    } else {
        androidx.compose.ui.graphics.Brush.verticalGradient(
            0f to Color(0x1F1C1504),
            0.58f to Color(0x9E1C1504),
            1f to Color(0xE61C1504),
        )
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(108.dp)
            // Sin foto el fondo va blanco: el marrón oscuro pesaba
            // mucho a la vista. Con foto, marrón mientras carga.
            .background(if (imageUrl.isNullOrBlank()) Color.White else BrandBrown),
    ) {
        if (!imageUrl.isNullOrBlank()) {
            AsyncImage(
                model = imageUrl,
                // null a propósito: la tarjeta COMPLETA ya es clicable
                // y su Text expone el nombre. Si además le pusiéramos
                // contentDescription, TalkBack leería el nombre dos veces.
                contentDescription = null,
                contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            PlaceholderBrand(modifier = Modifier.align(Alignment.Center))
        }

        // Velo marrón: el nombre se lee sobre cualquier foto
        Box(modifier = Modifier.fillMaxSize().background(veil))

        // Punto de estado, esquina superior izquierda. Con anillo blanco:
        // los tonos de estado son ya oscuros y así se separan del velo.
        Box(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(7.dp)
                .size(11.dp)
                .clip(CircleShape)
                .background(statusColor)
                .border(1.5.dp, Color.White, CircleShape),
        )

        // Título + categoría + pastilla "Destacado" encima de la foto
        Column(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .fillMaxWidth()
                .padding(horizontal = 9.dp, vertical = 8.dp),
        ) {
            Text(
                text = business.name,
                color = Color.White,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            Spacer(Modifier.height(2.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = (business.category_name
                        ?: stringResource(R.string.home_no_category)).uppercase(),
                    color = CanaryYellow,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )

                if (featured) {
                    Spacer(Modifier.width(6.dp))
                    DestacadoBadge()
                }
            }
        }
    }
}

/**
 * Placeholder de marca (espejo del de la web): el logotipo al 50%
 * de opacidad sobre fondo blanco. Es texto pintado (sin BD ni
 * storage), y así la tarjeta SIEMPRE muestra algo.
 */
@Composable
private fun PlaceholderBrand(modifier: Modifier = Modifier) {
    Row(modifier = modifier) {
        Text(
            text = "Buscando",
            color = BrandBrown.copy(alpha = 0.5f),
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 1.sp,
        )
        Text(
            text = "Ando",
            color = Gold.copy(alpha = 0.5f),
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 1.sp,
        )
    }
}

/**
 * Pastilla "Destacado".
 *
 * Espejo de `.biz-card__badge` de la web: blanca, texto dorado
 * (#8F6C14) y 6dp de radio. Sustituye a la antigua pastilla de nivel.
 */
@Composable
private fun DestacadoBadge(modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(6.dp)
    Box(
        modifier = modifier
            .clip(shape)
            .background(Color.White)
            // Filete fino como .biz-card__badge de la web
            .border(1.dp, Color(0x261F1A1A), shape)
            .padding(horizontal = 8.dp, vertical = 2.dp),
    ) {
        Text(
            text = stringResource(R.string.card_featured),
            color = GoldInk,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
        )
    }
}

@Composable
private fun StatusBadge(business: Business) {
    val color = statusColorOf(business.effective_status)

    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(7.dp)
                .clip(CircleShape)
                .background(color),
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text = business.effective_status_name ?: "—",
            color = color,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

// ═══════════════════════ PAGINACIÓN ═══════════════════════

@Composable
private fun PaginationBar(
    state: HomeUiState,
    onPreviousPage: () -> Unit,
    onNextPage: () -> Unit,
) {
    HorizontalDivider(color = Hairline, thickness = 1.dp)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(CanvasWhite)
            // Espacio para la barra de navegación (gestos / botones)
            .navigationBarsPadding()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(
            onClick = onPreviousPage,
            enabled = state.canGoPrevious,
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                contentDescription = stringResource(R.string.home_prev_page),
                tint = if (state.canGoPrevious) GoldInk else TextMuted,
            )
        }

        Column(
            modifier = Modifier.weight(1f),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = stringResource(
                    R.string.home_page_of,
                    state.currentPage,
                    state.totalPages,
                ),
                color = TextPrimary,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = stringResource(R.string.home_total_results, state.totalCount),
                color = TextMuted,
                style = MaterialTheme.typography.labelSmall,
            )
        }

        IconButton(
            onClick = onNextPage,
            enabled = state.canGoNext,
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = stringResource(R.string.home_next_page),
                tint = if (state.canGoNext) GoldInk else TextMuted,
            )
        }
    }
}

// ═══════════════════════ ESTADOS ═══════════════════════

@Composable
private fun CenteredMessage(
    modifier: Modifier,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = modifier.fillMaxWidth().padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) { content() }
    }
}

@Composable
private fun ErrorState(
    modifier: Modifier,
    message: String,
    onRetry: () -> Unit,
) {
    CenteredMessage(modifier) {
        Icon(
            imageVector = Icons.Default.Warning,
            contentDescription = null,
            tint = StatusClosed,
            modifier = Modifier.size(40.dp),
        )
        Spacer(Modifier.height(12.dp))
        Text(
            text = stringResource(R.string.home_error_retry),
            color = TextPrimary,
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            text = message,
            color = TextMuted,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(16.dp))
        OutlinedButton(
            onClick = onRetry,
            border = androidx.compose.foundation.BorderStroke(1.dp, CanaryYellow),
        ) {
            Icon(
                imageVector = Icons.Default.Refresh,
                contentDescription = null,
                tint = GoldInk,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(text = stringResource(R.string.home_error_retry), color = GoldInk)
        }
    }
}

@Composable
private fun ErrorBanner(message: String, onRetry: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            // Banda de error: tinte rojo muy suave sobre el lienzo
            // blanco, como los avisos de la web (nada de fondo oscuro).
            .background(Color(0x14DC2626))
            // 4dp + los 40dp mínimos de TextButton = 48dp de alto total.
            .padding(horizontal = 14.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Default.Warning,
            contentDescription = null,
            tint = StatusClosed,
            modifier = Modifier.size(16.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = message,
            color = TextSecondary,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Spacer(Modifier.width(8.dp))
        // ACCESIBILIDAD: era un Text con .clickable + padding(4dp),
        // o sea una zona de toque de ~24dp. TextButton trae de fábrica
        // el tamaño mínimo y el centrado, y con padding horizontal
        // fijo conserva el aspecto de "enlace" dentro del banner.
        TextButton(
            onClick = onRetry,
            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp),
        ) {
            Text(
                text = stringResource(R.string.home_error_retry),
                color = GoldInk,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

// ═══════════════════════ RESULTADOS ═══════════════════════

/**
 * Cabecera de la rejilla: "Buscando…" o "12 resultados".
 *
 * Espejo de `.right-section-header` de Home.jsx: solo EXISTE tras la
 * primera consulta — en portada no hay nada que contar.
 */
@Composable
private fun ResultsHeader(state: HomeUiState) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 14.dp, top = 12.dp, end = 14.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = if (state.isLoading) {
                stringResource(R.string.home_results_loading)
            } else {
                stringResource(R.string.home_results_count, state.totalCount)
            },
            color = TextPrimary,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

// ═══════════════════════ PORTADA (R1.1) ═══════════════════════

/**
 * El aviso de "todavía no hay punto activo".
 *
 * Solo aparece cuando NO hay punto: con punto el usuario ya tiene un
 * círculo de 5 km trazado y el aviso sería mentira.
 */
@Composable
private fun portadaHint(state: HomeUiState): String? =
    if (state.sinPunto) stringResource(R.string.home_portada_hint) else null

/** Las 6 frases de MapOverlay.jsx (ninguna nombra un municipio). */
private val PORTADA_MENSAJES = listOf(
    R.string.home_portada_msg_1,
    R.string.home_portada_msg_2,
    R.string.home_portada_msg_3,
    R.string.home_portada_msg_4,
    R.string.home_portada_msg_5,
    R.string.home_portada_msg_6,
)

/**
 * La portada de la web, adaptada al formato vertical.
 *
 * Espejo de `MapOverlay.jsx` + `.right-portada` de Home.jsx: logotipo
 * animado, frase que rota cada 3,5 s con fundido de 400 ms, el aviso
 * de cómo empezar cuando no hay punto, y los puntos indicadores.
 *
 * Se usa en DOS sitios, igual que en la web:
 *  - `!haBuscado` → ocupa el hueco de la rejilla (la portada),
 *  - `isEmpty`    → el overlay de "sin resultados".
 */
@Composable
private fun PortadaOverlay(modifier: Modifier = Modifier, hint: String?) {
    var indice by remember { mutableIntStateOf(0) }
    var oculto by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        while (true) {
            delay(3500)
            oculto = true
            delay(400)
            indice = (indice + 1) % PORTADA_MENSAJES.size
            oculto = false
        }
    }

    val alpha by animateFloatAsState(
        targetValue = if (oculto) 0f else 1f,
        animationSpec = tween(durationMillis = 400),
        label = "portadaFade",
    )

    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(CanvasWhite)
            .padding(horizontal = 24.dp, vertical = 18.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            PortadaLogo()

            Spacer(Modifier.height(14.dp))

            // Mismo logotipo que la web: "Buscando" dorado y "Ando"
            // amarillo (los dos colores de .map-overlay__title).
            Row {
                Text(
                    text = "Buscando",
                    color = GoldInk,
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 2.sp,
                )
                Text(
                    text = "Ando",
                    color = CanaryYellow,
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 2.sp,
                )
            }

            Spacer(Modifier.height(16.dp))

            Text(
                text = stringResource(PORTADA_MENSAJES[indice]),
                color = TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                letterSpacing = 0.5.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.graphicsLayer { this.alpha = alpha },
            )

            if (hint != null) {
                Spacer(Modifier.height(14.dp))
                Text(
                    text = hint,
                    color = GoldInk,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.4.sp,
                    textAlign = TextAlign.Center,
                )
            }

            Spacer(Modifier.height(18.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                PORTADA_MENSAJES.forEachIndexed { i, _ ->
                    val activo = i == indice
                    Box(
                        modifier = Modifier
                            .height(6.dp)
                            .width(if (activo) 18.dp else 6.dp)
                            .clip(RoundedCornerShape(if (activo) 3.dp else 50.dp))
                            .background(if (activo) CanaryYellow else Color(0x381A1A1A)),
                    )
                }
            }
        }
    }
}

/**
 * El logotipo animado de la portada: aro exterior que gira, aro
 * interior, chinchete que rebota y anillo que pulsa — las tres
 * animaciones de `.map-overlay__*` de MapOverlay.css.
 */
@Composable
private fun PortadaLogo() {
    val transicion = rememberInfiniteTransition(label = "portadaLogo")

    val giro by transicion.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(durationMillis = 20_000)),
        label = "giro",
    )
    val rebote by transicion.animateFloat(
        initialValue = 0f,
        targetValue = -6f,
        animationSpec = infiniteRepeatable(tween(durationMillis = 1_000), RepeatMode.Reverse),
        label = "rebote",
    )
    val pulso by transicion.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(durationMillis = 2_000)),
        label = "pulso",
    )

    Box(modifier = Modifier.size(104.dp), contentAlignment = Alignment.Center) {
        // Anillo que se expande y se desvanece (pulseRing de la web)
        Box(
            modifier = Modifier
                .size(56.dp)
                .graphicsLayer {
                    scaleX = 1f + pulso * 1.1f
                    scaleY = 1f + pulso * 1.1f
                    alpha = (1f - pulso) * 0.8f
                }
                .border(1.5.dp, BrandBrown, CircleShape),
        )

        // Aro exterior girando (stroke-dasharray + spinSlow de la web)
        Box(
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer { rotationZ = giro }
                .border(2.dp, BrandBrown, CircleShape),
        )

        // Aro interior, girando al revés en la web; aquí es estático
        // porque sin discontinuidad no se ve el movimiento.
        Box(
            modifier = Modifier
                .size(84.dp)
                .border(1.dp, BrandBrown.copy(alpha = 0.35f), CircleShape),
        )

        // El chinchete: contorno marrón + relleno amarillo, que es lo
        // que hace legible la aguja sobre el blanco.
        Box(contentAlignment = Alignment.Center) {
            Icon(
                imageVector = Icons.Default.Place,
                contentDescription = null,
                tint = BrandBrown,
                modifier = Modifier
                    .size(56.dp)
                    .graphicsLayer { translationY = rebote },
            )
            Icon(
                imageVector = Icons.Default.Place,
                contentDescription = null,
                tint = CanaryYellow,
                modifier = Modifier
                    .size(46.dp)
                    .graphicsLayer { translationY = rebote },
            )
        }
    }
}

// ═══════════════════════ MUNICIPIO (R3.4) ═══════════════════════

/**
 * Selector de municipio: el `<select class="municipio-group">` de
 * SearchBar.jsx hecho para el dedo.
 *
 * La web lo deja FUERA de "Filtros" a propósito (R1.1): quien niega la
 * ubicación tiene que llegar al selector en un toque, si no se queda
 * mirando el overlay sin salida. Aquí va igual, siempre visible bajo
 * el buscador.
 */
@Composable
private fun MunicipioSelector(
    clave: String,
    cabeceras: List<Cabecera>,
    onSelect: (Cabecera?) -> Unit,
) {
    var abierto by remember { mutableStateOf(false) }
    val shape = RoundedCornerShape(8.dp)

    // El <option> de la web muestra SOLO el nombre del municipio; la
    // provincia está en la clave porque puede haber homónimos.
    val nombre = clave.split('~').getOrNull(1)?.takeIf { it.isNotBlank() }

    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = stringResource(R.string.home_municipio_label),
            color = TextMuted,
            style = MaterialTheme.typography.labelMedium,
        )

        Spacer(Modifier.height(4.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(shape)
                .background(SurfaceWhite)
                .border(1.dp, HairlineStrong, shape)
                .clickable(enabled = cabeceras.isNotEmpty()) { abierto = true }
                .padding(horizontal = 12.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Default.Place,
                contentDescription = null,
                tint = if (nombre != null) GoldInk else TextSecondary,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(
                text = nombre ?: stringResource(
                    if (cabeceras.isEmpty()) R.string.home_municipio_loading
                    else R.string.home_municipio_empty,
                ),
                color = if (nombre != null) TextPrimary else TextMuted,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = Icons.Default.ArrowDropDown,
                contentDescription = null,
                tint = TextSecondary,
            )
        }
    }

    if (abierto) {
        MunicipioPickerDialog(
            clave = clave,
            cabeceras = cabeceras,
            onDismiss = { abierto = false },
            onSelect = { cabecera ->
                onSelect(cabecera)
                abierto = false
            },
        )
    }
}

/**
 * Diálogo con los 158 municipios, agrupados por provincia y con un
 * campo de filtro (sin tildes y en cualquier orden, como la búsqueda).
 *
 * En la web es un `<optgroup>` con 158 `<option>`; en un teléfono eso
 * es ilegible, así que se abre a pantalla completa con buscador.
 */
@Composable
private fun MunicipioPickerDialog(
    clave: String,
    cabeceras: List<Cabecera>,
    onDismiss: () -> Unit,
    onSelect: (Cabecera?) -> Unit,
) {
    var filtro by remember { mutableStateOf("") }
    val grupos = remember(cabeceras) { agruparPorProvincia(cabeceras) }
    val visibles = remember(grupos, filtro) { filtrarGrupos(grupos, filtro) }

    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = CardWhite,
            border = BorderStroke(1.dp, Hairline),
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 640.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 10.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = stringResource(R.string.home_municipio_label),
                        color = TextPrimary,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(onClick = onDismiss) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = stringResource(R.string.home_municipio_close),
                            tint = TextSecondary,
                        )
                    }
                }

                Spacer(Modifier.height(6.dp))

                OutlinedTextField(
                    value = filtro,
                    onValueChange = { filtro = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = {
                        Text(
                            text = stringResource(R.string.home_municipio_hint),
                            color = TextMuted,
                        )
                    },
                    singleLine = true,
                    leadingIcon = {
                        Icon(
                            imageVector = Icons.Default.Search,
                            contentDescription = null,
                            tint = TextSecondary,
                        )
                    },
                    shape = RoundedCornerShape(8.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = CanaryYellow,
                        unfocusedBorderColor = HairlineStrong,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        cursorColor = GoldInk,
                        focusedContainerColor = SurfaceWhite,
                        unfocusedContainerColor = SurfaceWhite,
                    ),
                )

                if (clave != "") {
                    TextButton(onClick = { onSelect(null) }) {
                        Text(
                            text = stringResource(R.string.home_municipio_clear),
                            color = GoldInk,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    HorizontalDivider(color = Hairline, thickness = 1.dp)
                }

                when {
                    cabeceras.isEmpty() -> CenteredMessage(Modifier.heightIn(min = 140.dp)) {
                        CircularProgressIndicator(color = GoldInk, strokeWidth = 3.dp)
                    }

                    visibles.isEmpty() -> CenteredMessage(Modifier.heightIn(min = 140.dp)) {
                        Text(
                            text = stringResource(R.string.home_municipio_empty_list),
                            color = TextMuted,
                            style = MaterialTheme.typography.bodyMedium,
                            textAlign = TextAlign.Center,
                        )
                    }

                    else -> LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 420.dp),
                    ) {
                        visibles.forEach { grupo ->
                            item(key = "provincia-${grupo.provincia}") {
                                Text(
                                    text = grupo.provincia,
                                    color = GoldInk,
                                    style = MaterialTheme.typography.labelLarge,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier.padding(top = 10.dp, bottom = 4.dp),
                                )
                            }
                            items(grupo.lista, key = { it.clave }) { cabecera ->
                                val activa = cabecera.clave == clave
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { onSelect(cabecera) }
                                        .padding(vertical = 10.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text(
                                        text = cabecera.municipio,
                                        color = if (activa) GoldInk else TextPrimary,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = if (activa) FontWeight.Bold else FontWeight.Normal,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                        modifier = Modifier.weight(1f),
                                    )
                                    if (activa) {
                                        Icon(
                                            imageVector = Icons.Default.Place,
                                            contentDescription = null,
                                            tint = GoldInk,
                                            modifier = Modifier.size(16.dp),
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/** Un grupo del selector: provincia + sus municipios ordenados. */
private data class GrupoProvincia(val provincia: String, val lista: List<Cabecera>)

/**
 * Agrupa las cabeceras como el `<optgroup>` de la web: provincias
 * ordenadas y municipios ordenados dentro de cada una, con colación
 * española (¡Caños!, ¡Cordero!) para que "Íñigo" no acabe en la I.
 */
private fun agruparPorProvincia(cabeceras: List<Cabecera>): List<GrupoProvincia> {
    val collator = Collator.getInstance(Locale("es"))
    return cabeceras
        .groupBy { it.provincia }
        .map { (provincia, lista) ->
            GrupoProvincia(provincia, lista.sortedWith(compareBy(collator) { it.municipio }))
        }
        .sortedWith(compareBy(collator) { it.provincia })
}

private fun filtrarGrupos(grupos: List<GrupoProvincia>, texto: String): List<GrupoProvincia> {
    val consulta = normalizar(texto)
    if (consulta.isBlank()) return grupos
    return grupos.mapNotNull { grupo ->
        val lista = grupo.lista.filter {
            normalizar(it.municipio).contains(consulta) ||
                normalizar(it.provincia).contains(consulta)
        }
        if (lista.isEmpty()) null else GrupoProvincia(grupo.provincia, lista)
    }
}

/** Quita tildes y pasa a minúsculas: "SÁNCHEZ" encuentra "sanchez". */
private fun normalizar(texto: String): String =
    Normalizer.normalize(texto, Normalizer.Form.NFD)
        .replace(Regex("\\p{M}"), "")
        .lowercase(Locale.ROOT)

// ═══════════════════════ HELPERS ═══════════════════════

/** Mapea el slug del estado operativo al color de la paleta. */
internal fun statusColorOf(slug: String?): Color = when (slug) {
    "abierto" -> StatusOpen
    "cerrado" -> StatusClosed
    "por-horario" -> StatusBySchedule
    else -> GreyOlive
}
