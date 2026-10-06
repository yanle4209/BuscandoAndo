package com.herling.buscandoando.ui.home

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
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
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil3.compose.AsyncImage
import com.herling.buscandoando.R
import com.herling.buscandoando.core.data.FeaturedTier
import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.location.getCurrentCoordinates
import com.herling.buscandoando.ui.iconForCategory
import com.herling.buscandoando.ui.theme.CanaryYellow
import com.herling.buscandoando.ui.theme.DarkBackground
import com.herling.buscandoando.ui.theme.BrandBrown
import com.herling.buscandoando.ui.theme.DarkCard
import com.herling.buscandoando.ui.theme.DarkSurface
import com.herling.buscandoando.ui.theme.DividerDark
import com.herling.buscandoando.ui.theme.FeaturedBorder
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
import kotlinx.coroutines.launch

/** Etiqueta para logcat (Fase 6: seguir el GPS desde Android Studio). */
private const val TAG = "BuscandoAndo"

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

    // ═══════════ FASE 6 · permiso y GPS ═══════════
    //
    // La composable es la ÚNICA que habla con el sistema operativo
    // (diálogo de permisos, GPS). El ViewModel solo sabe de estados.
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    /**
     * Ir a buscar las coordenadas.
     *
     * Nota el orden: se declara ANTES del `permissionLauncher` porque
     * el callback de éste lo usa. En Kotlin un local fun no puede
     * referenciar algo declarado más abajo.
     */
    fun fetchCoordinates() {
        viewModel.onStartLocating()
        scope.launch {
            // getCurrentCoordinates devuelve null si no hay permiso,
            // si no hay GPS o si algo falla -> mismo estado "Denied".
            val location = context.getCurrentCoordinates()
            Log.d(TAG, "fix = ${location?.latitude}, ${location?.longitude}")
            if (location == null) viewModel.onLocationFailed()
            else viewModel.onLocationAcquired(location.latitude, location.longitude)
        }
    }

    /**
     * Diálogo del sistema de Android: "¿Permitir a BuscandoAndo usar
     * la ubicación del dispositivo?".
     *
     * Es un "contrato de actividad": lanza el diálogo y devuelve el
     * resultado como callback. Si el usuario marcó "No volver a
     * preguntar", Android responde `false` al instante y caemos en
     * el estado Denied (por eso ese estado ofrece "Ajustes").
     */
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) fetchCoordinates() else viewModel.onLocationFailed()
    }

    fun requestLocation() {
        val granted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED

        if (granted) {
            fetchCoordinates()          // ya lo tiene: directo al GPS
        } else {
            permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
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
    // fallo de CATEGORÍAS, que antes desaparecía en silencio (los chips
    // son "nice to have" y su error se traga a propósito).
    //
    // NO lo usamos para el fallo de BÚSQUEDA: ahí ya hay un banner
    // fijo con botón "Reintentar", que es mejor porque no caduca.
    val snackbarHostState = remember { SnackbarHostState() }
    val categoriesErrorMessage = stringResource(R.string.home_categories_error)

    LaunchedEffect(state.categoriesError) {
        if (state.categoriesError) snackbarHostState.showSnackbar(categoriesErrorMessage)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            // Los insets del sistema: sin esto el título queda DETRÁS
            // del reloj/batería. statusBarsPadding = espacio arriba.
            .statusBarsPadding()
            // Ajusta el contenido cuando sube el teclado (IME)
            .imePadding(),
    ) {
        // ── Cabecera fija: título + buscador + chips ──
        HomeHeader(
            state = state,
            onQueryChange = onQueryChange,
            onSearch = onSearch,
            onCategorySelected = onCategorySelected,
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

        HorizontalDivider(color = DividerDark, thickness = 1.dp)

        // ── Cuerpo: carga / error / vacío / cuadrícula ──
        when {
            state.isLoading && state.businesses.isEmpty() ->
                CenteredMessage(Modifier.weight(1f)) {
                    CircularProgressIndicator(color = CanaryYellow, strokeWidth = 3.dp)
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
                CenteredMessage(Modifier.weight(1f)) {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = null,
                        tint = TextSecondary,
                        modifier = Modifier.size(40.dp),
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = stringResource(R.string.home_empty),
                        color = TextPrimary,
                        style = MaterialTheme.typography.titleMedium,
                        textAlign = TextAlign.Center,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = stringResource(R.string.home_empty_hint),
                        color = TextMuted,
                        style = MaterialTheme.typography.bodySmall,
                        textAlign = TextAlign.Center,
                    )
                }

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

        // ── Paginación ──
        if (state.businesses.isNotEmpty()) {
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
                    color = CanaryYellow,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Black,
                )
                Text(
                    text = "Moca · Espaillat",
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
                        color = CanaryYellow,
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
                        tint = if (state.hasLocation) CanaryYellow else TextSecondary,
                    )
                }
            }

            IconButton(onClick = onOpenMap) {
                Icon(
                    imageVector = Icons.Default.Map,
                    contentDescription = stringResource(R.string.home_open_map),
                    tint = CanaryYellow,
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

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp)) {
        when (state.locationStatus) {
            LocationStatus.Idle -> Unit   // ya salimos arriba

            LocationStatus.Locating -> Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(top = 2.dp, bottom = 12.dp),
            ) {
                CircularProgressIndicator(
                    color = CanaryYellow,
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
                        tint = CanaryYellow,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = stringResource(R.string.home_near_me),
                        color = CanaryYellow,
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
                            color = CanaryYellow,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    TextButton(onClick = onOpenSettings) {
                        Text(
                            text = stringResource(R.string.home_open_settings),
                            color = CanaryYellow,
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

    val shape = RoundedCornerShape(12.dp)

    // Glow: animamos elevación (la sombra) y el color del borde
    val elevation by animateDpAsState(
        targetValue = if (focused) 10.dp else 0.dp,
        label = "glowElevation",
    )
    val borderColor by animateColorAsState(
        targetValue = if (focused) CanaryYellow else DividerDark,
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
            .background(DarkSurface)
            .border(1.5.dp, borderColor, shape),
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
                    tint = if (focused) CanaryYellow else TextSecondary,
                )
            },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = { onQueryChange("") }) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            // Sin esto TalkBack anuncia "activar" y nada más.
                            contentDescription = stringResource(R.string.home_search_clear),
                            tint = TextSecondary,
                        )
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
                cursorColor = CanaryYellow,
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
            .background(if (selected) CanaryYellow else DarkCard)
            .border(1.dp, if (selected) CanaryYellow else DividerDark, shape)
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
 * Fila horizontal de destacados de la BÚSQUEDA.
 *
 * Espejo de `searchFeatured` en Home.jsx: hasta 3 tarjetas que el
 * endpoint /api/businesses/featured-by-search/ devuelve y que la web
 * pinta POR ENCIMA de los resultados.
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

        LazyRow(
            contentPadding = PaddingValues(horizontal = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(featured, key = { "destacado-${it.id}" }) { business ->
                FeaturedCard(business = business, onClick = { onBusinessClick(business) })
            }
        }
    }
}

/**
 * Tarjeta compacta de la fila de destacados.
 *
 * NO reutiliza BusinessCard: ésta tiene ancho FIJO y no lleva imagen,
 * para que 3 quepan en horizontal sin robarle alto a la cuadrícula.
 */
@Composable
private fun FeaturedCard(business: Business, onClick: () -> Unit) {
    val featured = business.is_featured == true ||
        FeaturedTier.levelOf(business.featured_tier) != null
    val shape = RoundedCornerShape(10.dp)

    Column(
        modifier = Modifier
            .width(170.dp)
            .heightIn(min = 100.dp)
            .clip(shape)
            .background(DarkCard)
            // Sin escalonado por nivel: borde fino para todas y filete
            // amarillo solo en las destacadas, igual que la web.
            .border(1.dp, if (featured) FeaturedBorder else DividerDark, shape)
            .clickable(onClick = onClick)
            .padding(9.dp),
    ) {
        if (featured) {
            DestacadoBadge()
            Spacer(Modifier.height(6.dp))
        }

        Text(
            text = business.name,
            color = TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )

        Spacer(Modifier.height(4.dp))

        Text(
            text = business.category_name ?: stringResource(R.string.home_no_category),
            color = TextMuted,
            style = MaterialTheme.typography.labelSmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

// ═══════════════════════ CUADRÍCULA ═══════════════════════

/**
 * Tarjetas. `Adaptive(150.dp)` da 2 columnas en teléfono y 4 en
 * tablet — el mismo "espíritu" de la cuadrícula 4x3 de la web sin
 * partir los nombres en 4 letras.
 */
@Composable
private fun BusinessGrid(
    state: HomeUiState,
    modifier: Modifier,
    onBusinessClick: (Business) -> Unit,
) {
    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 150.dp),
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
    // lo mismo y solo cambia el filete de las destacadas.
    val featured = business.is_featured == true ||
        FeaturedTier.levelOf(business.featured_tier) != null
    val shape = RoundedCornerShape(10.dp)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            // Altura MINIMA fija: portada 108 + cuerpo (estado + padding).
            // La foto no puede hacer crecer la tarjeta.
            .heightIn(min = 152.dp)
            .clip(shape)
            .background(DarkCard)
            .border(1.dp, if (featured) FeaturedBorder else DividerDark, shape)
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
    val veil = androidx.compose.ui.graphics.Brush.verticalGradient(
        0f to Color.Transparent,
        0.45f to Color(0x991C1504),
        1f to Color(0xF21C1504),
    )

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

        // Punto de estado, esquina superior izquierda
        Box(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(7.dp)
                .size(11.dp)
                .clip(CircleShape)
                .background(statusColor),
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
    HorizontalDivider(color = DividerDark, thickness = 1.dp)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(DarkBackground)
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
                tint = if (state.canGoPrevious) CanaryYellow else TextMuted,
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
                tint = if (state.canGoNext) CanaryYellow else TextMuted,
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
                tint = CanaryYellow,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(text = stringResource(R.string.home_error_retry), color = CanaryYellow)
        }
    }
}

@Composable
private fun ErrorBanner(message: String, onRetry: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF3A2A2A))
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
                color = CanaryYellow,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

// ═══════════════════════ HELPERS ═══════════════════════

/** Mapea el slug del estado operativo al color de la paleta. */
internal fun statusColorOf(slug: String?): Color = when (slug) {
    "abierto" -> StatusOpen
    "cerrado" -> StatusClosed
    "por-horario" -> StatusBySchedule
    else -> GreyOlive
}
