package com.herling.buscandoando.core.location

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.os.Looper
import androidx.core.content.ContextCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import kotlin.coroutines.resume
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * FASE 6 — Acceso al GPS.
 *
 * ── La lección de arquitectura ──────────────────────────────────────
 *
 * Esta función NO pide permisos. Solo dice:
 * "si ya lo tienes, te doy las coordenadas".
 *
 * La política de permisos vive en la UI (HomeScreen), porque solo
 * ahí podemos mostrar un diálogo y explicar al usuario POR QUÉ lo
 * necesitamos. Si la capa de datos pidiera permisos, no tendría cómo
 * hablar con la persona.
 *
 *   Capa       ¿Pide permiso?   ¿Pide coordenadas?
 *   ────────   ──────────────   ───────────────────
 *   UI (Home)       ✅                 ❌
 *   Datos (esta)    ❌                 ✅
 *
 * ── Task de Play Services → corrutina ──────────────────────────────
 *
 * `FusedLocationProviderClient` devuelve un `Task<T>` (callback-based).
 * `suspendCancellableCoroutine` lo convierte en algo que se puede
 * `await`... es decir, el puente entre el mundo de los callbacks
 * (Java/Play Services) y el mundo de las corrutinas (Kotlin).
 *
 * Es el equivalente Android de:
 *
 *   const data = await new Promise(resolve => task.then(resolve));
 *
 * ── Los dos "límites de frescura" ──────────────────────────────────
 *
 * `lastLocation` es "lo último que se vio", que puede ser de HACE
 * HORAS (en el emulador pasa siempre: devuelve la posición por
 * defecto). Filtrar "cerca de mí" con una posición vieja engaña al
 * usuario, así que solo la usamos si es reciente... pero TAMPOCO
 * descartamos todo si el GPS no responde: un cache de hace 20 min
 * sigue siendo mejor que no filtrar nada.
 */

/** Camino rápido: el cache vale si tiene menos de 2 minutos. */
private const val FRESH_FIX_MS = 2 * 60 * 1000L

/** Último recurso: si el GPS falló, aceptamos el cache hasta 30 min. */
private const val MAX_STALE_FIX_MS = 30 * 60 * 1000L

/**
 * ¿Tenemos permiso para mirar la ubicación?
 *
 * Acepta FINE **o** COARSE. Es importante: en Android 12+ el diálogo del
 * sistema ofrece "Aproximada" (solo COARSE) y si la app solo mirara FINE
 * daría por denegado un permiso que el usuario SÍ concedió — y con un
 * radio de 5 km la precisión de celda es de sobra.
 */
fun Context.hasLocationPermission(): Boolean {
    val fine = ContextCompat.checkSelfPermission(
        this, Manifest.permission.ACCESS_FINE_LOCATION,
    ) == PackageManager.PERMISSION_GRANTED
    if (fine) return true
    return ContextCompat.checkSelfPermission(
        this, Manifest.permission.ACCESS_COARSE_LOCATION,
    ) == PackageManager.PERMISSION_GRANTED
}

/**
 * Devuelve la posición actual, o `null` si no hay permiso, no hay GPS
 * o algo falla.
 *
 * Estrategia en tres pasos, del más barato al más caro:
 *
 *  1. `lastLocation` si es reciente → gratis, no enciende el GPS.
 *  2. `getCurrentLocation`         → fix nuevo (1-4 s, batería).
 *  3. `lastLocation` aunque sea viejo → el plan B cuando el GPS
 *                                    no respondió en el paso 2.
 */
suspend fun Context.getCurrentCoordinates(): Location? {

    // Comprobación defensiva: así nunca lanzamos SecurityException.
    // Acepta FINE o COARSE (ver hasLocationPermission).
    if (!hasLocationPermission()) return null

    val fused = LocationServices.getFusedLocationProviderClient(this)

    // ── 1. Cache reciente ──
    val cached = awaitLastLocation(fused)
    if (cached != null && cached.isYoungerThan(FRESH_FIX_MS)) return cached

    // ── 2. Fix nuevo ──
    val fresh = awaitFreshLocation(fused)
    if (fresh != null) return fresh

    // ── 3. Plan B ──
    return cached?.takeIf { it.isYoungerThan(MAX_STALE_FIX_MS) }
}

/** "Lo último que se vio" (o null si nunca se vio nada). */
private suspend fun awaitLastLocation(
    client: FusedLocationProviderClient,
): Location? = suspendCancellableCoroutine { cont ->
    client.lastLocation
        .addOnSuccessListener { if (cont.isActive) cont.resume(it) }
        .addOnFailureListener { if (cont.isActive) cont.resume(null) }
}

/**
 * Pide al GPS un fix nuevo.
 *
 * `CancellationTokenSource` es la versión Play Services de
 * `job.cancel()`: si la corrutina que lo llama se cancela (por
 * ejemplo, el usuario cierra la pantalla), se corta la petición.
 */
private suspend fun awaitFreshLocation(
    client: FusedLocationProviderClient,
): Location? {
    val token = CancellationTokenSource().token
    return suspendCancellableCoroutine { cont ->
        client.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, token)
            .addOnSuccessListener { if (cont.isActive) cont.resume(it) }
            .addOnFailureListener { if (cont.isActive) cont.resume(null) }
    }
}

private fun Location.isYoungerThan(maxAgeMs: Long): Boolean =
    System.currentTimeMillis() - time < maxAgeMs

/**
 * `watchPosition` de la web: un STREAM de posiciones mientras te mueves.
 *
 * Equivale a (Home.jsx 316-321):
 *
 *   geo.watchPosition((p) => dispatch({ type: 'gps', pos }), …)
 *
 * Es la pieza que hace falta para el refresco automático por movimiento
 * (R1.a): sin ella la app solo sabría dónde estás AL PULSAR y se
 * quedaría con resultados viejos en cuanto caminas 500 m.
 *
 * ── callbackFlow: callbacks → corrutina ──────────────────────────────
 *
 * Play Services notifica con un `LocationCallback` (mundo de callbacks);
 * `callbackFlow` lo convierte en un `Flow` que se puede `collect`. Al
 * cancelarse el recolector, `awaitClose` desregistra el listener: sin
 * eso el GPS seguiría corriendo con la pantalla cerrada y matando la
 * batería.
 *
 * `minDistanceMeters = 100` evita un fix por segundo mientras
 * conducimos: la regla de negocio solo dispara a partir de 500 m, así
 * que llegar cada ~10 s moviéndote es de sobra.
 *
 * El permiso NO se pide aquí (misma regla que arriba): se comprueba y,
 * si no está, el flujo se cierra solo.
 */
@SuppressLint("MissingPermission")
fun Context.locationUpdates(
    intervalMs: Long = 10_000L,
    minDistanceMeters: Float = 100f,
): Flow<Location> = callbackFlow {
    if (!hasLocationPermission()) {
        close()
        return@callbackFlow
    }

    val fused = LocationServices.getFusedLocationProviderClient(this@locationUpdates)

    val callback = object : LocationCallback() {
        override fun onLocationResult(resultado: LocationResult) {
            val ultima = resultado.lastLocation ?: return
            trySend(ultima)
        }
    }

    val solicitud = LocationRequest.Builder(Priority.PRIORITY_BALANCED_POWER_ACCURACY, intervalMs)
        .setMinUpdateIntervalMillis(5_000L)
        .setMinUpdateDistanceMeters(minDistanceMeters)
        .build()

    try {
        fused.requestLocationUpdates(solicitud, callback, Looper.getMainLooper())
    } catch (e: SecurityException) {
        // El permiso se revocó entre la comprobación y el registro.
        close(e)
        return@callbackFlow
    }

    awaitClose { fused.removeLocationUpdates(callback) }
}
