package com.herling.buscandoando.ui.map

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.DrawableCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.herling.buscandoando.R
import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.ui.home.BusinessDetailSheet
import com.herling.buscandoando.ui.home.HomeViewModel
import com.herling.buscandoando.ui.home.Punto
import com.herling.buscandoando.ui.home.statusColorOf
import com.herling.buscandoando.ui.theme.BrandBrown
import com.herling.buscandoando.ui.theme.CanaryYellow
import com.herling.buscandoando.ui.theme.CanvasWhite
import com.herling.buscandoando.ui.theme.CardWhite
import com.herling.buscandoando.ui.theme.GoldInk
import com.herling.buscandoando.ui.theme.Hairline
import com.herling.buscandoando.ui.theme.TextMuted
import com.herling.buscandoando.ui.theme.TextSecondary
import com.herling.buscandoando.ui.theme.TextPrimary
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.events.MapEventsReceiver
import org.osmdroid.util.BoundingBox
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.MapEventsOverlay
import org.osmdroid.views.overlay.Marker

/** Moca, Espaillat — el centro de tu base de datos. */
private const val DEFAULT_LAT = 19.383738
private const val DEFAULT_LNG = -70.534247
private const val DEFAULT_ZOOM = 14.0

/**
 * FASE 5 — Pantalla de mapa.
 *
 * REGLA DE ORO igual que en las fases anteriores: **esta pantalla no
 * toca la red**. Pinta `state.businesses` (que ya descargó el
 * ViewModel) y le avisa dos cosas: "tocaron un punto" y "cerraron la
 * hoja".
 *
 *  React / web               Aquí
 *  ─────────────────────     ──────────────────────────────
 *  <MapContainer/>           AndroidView(factory = { MapView })
 *  <Marker position={..}/>   Marker(map) dentro de map.overlays
 *  onMarkerClick             setOnMarkerClickListener
 *  onMapClick                MapEventsOverlay (elige punto, H)
 *  USER_ICON (center)        Marker con map_point (mismo azul)
 *  navigate('/negocio/x')    BusinessDetailSheet (misma de la Fase 4)
 */
@Composable
fun MapScreen(
    viewModel: HomeViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(CanvasWhite),
    ) {
        BusinessMap(
            businesses = state.businesses,
            punto = state.punto,
            onMarkerClick = viewModel::onBusinessSelected,
            onMapClick = viewModel::onMapPointSelected,
            modifier = Modifier.fillMaxSize(),
        )

        MapTopBar(
            visible = state.businesses.count { it.latitude != null && it.longitude != null },
            onBack = onBack,
            modifier = Modifier.align(Alignment.TopCenter),
        )

        LegendPill(modifier = Modifier.align(Alignment.BottomCenter))

        // Mismo componente de la Fase 4 — el detalle del negocio es
        // idéntico venga de la tarjeta o del punto del mapa.
        if (state.detailSlug != null) {
            BusinessDetailSheet(
                state = state,
                onDismiss = viewModel::onCloseDetail,
                onRetry = viewModel::onRetryDetail,
            )
        }
    }
}

// ═══════════════════ EL MAPA ═══════════════════

/**
 * Puente Compose <-> MapView de osmdroid.
 *
 * `AndroidView` es el equivalente a envolver un widget clásico
 * (View/ViewGroup) en Compose — igual que `wrap-elm` en React:
 *
 *  factory  → se ejecuta UNA vez   ≈ useEffect(..., [])  + useRef
 *  update   → en cada recomposición ≈ useEffect(...) sin deps
 *  onRelease→ al salir              ≈ return () => cleanup
 */
@Composable
private fun BusinessMap(
    businesses: List<Business>,
    punto: Punto?,
    onMarkerClick: (String) -> Unit,
    onMapClick: (Double, Double) -> Unit,
    modifier: Modifier = Modifier,
) {
    /**
     * Última lista que ya "encajamos" en la cámara.
     *
     * Guardamos la REFERENCIA (identidad), no el contenido:
     *  - cambió la lista  -> cambió el resultado -> reencuadramos
     *  - abriste el detalle -> la lista es la MISMA referencia -> NO
     *    movemos la cámara, para no robarte el gesto de zoom/paneo.
     */
    var fitted by remember { mutableStateOf<List<Business>?>(null) }

    /** Último punto dibujado: solo recentrar cuando CAMBIA (R2.1). */
    var ultimoPunto by remember { mutableStateOf<Punto?>(null) }

    AndroidView(
        modifier = modifier,
        factory = { ctx ->
            initOsmdroid(ctx)   // ANTES del primer MapView

            MapView(ctx).apply {
                setTileSource(TileSourceFactory.DEFAULT_TILE_SOURCE)
                setMultiTouchControls(true)
                controller.setZoom(DEFAULT_ZOOM)
                controller.setCenter(GeoPoint(DEFAULT_LAT, DEFAULT_LNG))
                onResume()      // arranca el proveedor de teselas
            }
        },
        update = { map ->
            syncMarkers(map, businesses, punto, onMarkerClick, onMapClick)

            if (fitted !== businesses) {
                fitted = businesses
                // ⚠️ NO encuadramos dentro de `update`: en ese momento el
                // MapView todavía NO tiene medida (0 x 0) y pedirle un zoom
                // animado a un viewport sin proyección hace girar el hilo
                // principal al 100% CPU hasta que Android muestra el
                // diálogo de "no responde". `post` lo deja para el
                // siguiente ciclo, cuando ya hay layout.
                map.post { fitTo(map, businesses) }
            }

            // ── H · recentrar SOLO cuando cambia el punto (R2.1) ──
            //
            // Es el useEffect de `center` de MapView.jsx: se respeta el
            // zoom que tenga el usuario, y si el punto no cambia el mapa
            // se puede arrastrar sin que nadie lo devuelva. Va DESPUÉS
            // del encaje de negocios: al tocar el mapa manda el punto, y
            // los resultados, cuando lleguen, harán su fitTo en el
            // siguiente update (mismo orden que en la web).
            if (punto !== ultimoPunto) {
                ultimoPunto = punto
                val nuevo = punto
                if (nuevo != null) {
                    // `post`: dentro de `update` el MapView aún no tiene
                    // medida (misma razón que el fitTo de arriba).
                    map.post {
                        map.controller.setCenter(GeoPoint(nuevo.lat, nuevo.lng))
                    }
                }
            }
        },
        onRelease = { map ->
            map.onPause()
            map.onDetach()
        },
    )
}

/**
 * Reconstruye los puntos desde cero.
 *
 * "Recrear en vez de mutar" es el patrón más simple y evita el clásico
 * bug de markers huérfanos: si un negocio sale de los resultados, su
 * punto se va con la lista.
 *
 * El ORDEN de los overlays importa: osmdroid reparte los toques de
 * ARRIBA A ABAJO (overlaysReversed) y se queda en el primero que los
 * consuma, así que el receptor del mapa va PRIMERO y los pines
 * después — tocarse un pin abre su ficha, no mueve el punto.
 */
private fun syncMarkers(
    map: MapView,
    businesses: List<Business>,
    punto: Punto?,
    onMarkerClick: (String) -> Unit,
    onMapClick: (Double, Double) -> Unit,
) {
    map.overlays.clear()

    // ── H · tocar el mapa = elegir el punto de búsqueda ──
    //
    // Es el `map.on('click')` de MapView.jsx: un toque que no cayó
    // sobre ningún pin mueve el punto y consulta desde ahí (ya no el
    // municipio: HomeMachine.mapa limpia la clave del selector).
    //
    // Se RECREA en cada sync porque `clear()` se lleva por delante
    // todo lo que hubiera dentro.
    map.overlays.add(
        MapEventsOverlay(object : MapEventsReceiver {
            override fun singleTapConfirmedHelper(p: GeoPoint?): Boolean {
                if (p == null) return false
                onMapClick(p.latitude, p.longitude)
                return true
            }

            // La web no tiene menú largo en el mapa: se ignora.
            override fun longPressHelper(p: GeoPoint?): Boolean = false
        }),
    )

    // ── El punto ACTIVO (USER_ICON de la web: aro blanco + núcleo
    //    azul). Solo existe si hay punto que consultar ──
    if (punto != null) {
        Marker(map).apply {
            setPosition(GeoPoint(punto.lat, punto.lng))
            setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
            icon = ContextCompat.getDrawable(map.context, R.drawable.map_point)

            // Tocar el punto NO vuelve a elegirlo — y consume el toque
            // para que osmdroid no abra su ventana de información vacía.
            setOnMarkerClickListener { _, _ -> true }

            map.overlays.add(this)
        }
    }

    businesses.forEach { business ->
        val lat = business.latitude
        val lng = business.longitude
        if (lat == null || lng == null) return@forEach   // sin coords, sin punto

        Marker(map).apply {
            setPosition(GeoPoint(lat, lng))
            setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
            icon = pinTinted(map.context, business.effective_status)

            setOnMarkerClickListener { _, _ ->
                val slug = business.slug
                if (slug == null) {
                    false            // -> que osmdroid haga lo suyo
                } else {
                    onMarkerClick(slug)
                    true            // -> click consumido, no hay info window
                }
            }

            map.overlays.add(this)
        }
    }

    map.invalidate()   // "repinta" — sin esto no se ve nada nuevo
}

/** Pin teñido con el MISMO semáforo de las tarjetas. */
private fun pinTinted(context: Context, status: String?): android.graphics.drawable.Drawable? {
    val base = ContextCompat.getDrawable(context, R.drawable.marker_pin) ?: return null
    val wrapped = DrawableCompat.wrap(base.mutate())   // mutate = copia editable
    DrawableCompat.setTint(wrapped, statusColorOf(status).toArgb())
    return wrapped
}

/**
 * Mueve la cámara para que TODOS los puntos quepan en pantalla.
 *
 * Un punto solo  -> centro + zoom fijo.
 * Varios puntos  -> bounding box + 20% de margen.
 * Ninguno        -> nos quedamos donde estaba (Moca).
 */
private fun fitTo(map: MapView, businesses: List<Business>) {
    // Guarda: sin medida no hay proyección, y con proyección inválida
    // el cálculo del zoom sale infinito (ANR). Reintentamos al siguiente
    // ciclo hasta que el MapView tenga tamaño real.
    if (map.width == 0 || map.height == 0) {
        map.post { fitTo(map, businesses) }
        return
    }

    val points = businesses.mapNotNull { business ->
        val lat = business.latitude ?: return@mapNotNull null
        val lng = business.longitude ?: return@mapNotNull null
        GeoPoint(lat, lng)
    }

    when {
        points.isEmpty() -> Unit

        points.size == 1 -> {
            map.controller.setZoom(15.0)
            map.controller.setCenter(points.first())
        }

        else -> {
            val minLat = points.minOf { it.latitude }
            val maxLat = points.maxOf { it.latitude }
            val minLng = points.minOf { it.longitude }
            val maxLng = points.maxOf { it.longitude }

            // Suelo de 0.02° para no "dividir entre cero" si todas las
            // coordenadas son casi iguales; 20% de aire para que el pin
            // no quede pegado al borde.
            val padLat = (maxLat - minLat).coerceAtLeast(0.02) * 0.2
            val padLng = (maxLng - minLng).coerceAtLeast(0.02) * 0.2

            val bbox = BoundingBox(
                maxLat + padLat,   // north
                maxLng + padLng,   // east
                minLat - padLat,   // south
                minLng - padLng,   // west
            )
            // animated = false: el encuadre inicial es un salto. La
            // versión animada solo sirve si ya hay layout estable.
            map.zoomToBoundingBox(bbox, false, 48)   // 48 px de borde
        }
    }
}

// ═══════════════════ CAPAS SOBRE EL MAPA ═══════════════════

@Composable
private fun MapTopBar(
    visible: Int,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            // background ANTES de statusBarsPadding para que la barra
            // cubra también la franja del reloj/batería.
            .background(CardWhite)
            .statusBarsPadding()
            .padding(bottom = 4.dp),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(start = 2.dp, end = 12.dp, top = 2.dp),
        ) {
            IconButton(onClick = onBack) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = stringResource(R.string.map_back),
                    tint = TextPrimary,
                )
            }

            Column(Modifier.weight(1f)) {
                Text(
                    text = stringResource(R.string.map_title),
                    // Título marrón, igual que la cabecera de la web
                    color = BrandBrown,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Black,
                )
                Text(
                    text = stringResource(R.string.map_counter, visible),
                    color = GoldInk,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        // Filete amarillo 3dp bajo la barra: el mismo que separa la
        // cabecera de la web de su contenido.
        HorizontalDivider(color = CanaryYellow, thickness = 3.dp)
    }
}

@Composable
private fun LegendPill(modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(50)

    Box(
        modifier = modifier
            .navigationBarsPadding()
            .padding(bottom = 16.dp)
            .clip(shape)
            .background(CardWhite)
            .border(1.dp, Hairline, shape)
            .padding(horizontal = 18.dp, vertical = 9.dp),
    ) {
        Text(
            text = stringResource(R.string.map_legend),
            color = TextSecondary,
            style = MaterialTheme.typography.labelSmall,
        )
    }
}
