package com.herling.buscandoando.ui.home

import com.herling.buscandoando.core.data.dto.Cabecera
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.PI
import kotlin.math.sqrt

/**
 * La máquina de 3 estados + flag "llego" de DISENO.md §1, tal como vive
 * en Home.jsx (líneas 38-244). ESPEJO de esa función `reducer`.
 *
 * ── Por qué un objeto aparte del ViewModel ────────────────────────
 *
 * Es pura: entra un [HomeUiState], sale otro. No toca red, ni
 * SharedPreferences, ni Android, ni el tiempo. Eso la hace PROBARSE
 * sin emulador (HomeMachineTest) y la deja libre de efectos secundarios
 * — la misma razón por la que la web usa `useReducer` y no cinco
 * `useState` que se pisan entre sí.
 *
 *   Estado    Significado
 *   ────────  ──────────────────────────────────────────────────────
 *   espera    S0 · sin punto: NO se consulta nada (portada)
 *   gps       S1 · el punto es tu posición
 *   destino   S2 · el punto es un municipio elegido o un punto del mapa
 *
 *   llego     ya estuvo dentro del destino → habilita el reset R3.2
 *   restaurado el destino viene del almacén, no de una elección
 */
enum class SearchMode {
    /** S0 · Sin punto activo: no se consulta NADA (portada, R1.1). */
    Espera,

    /** S1 · El punto de consulta es tu posición GPS. */
    Gps,

    /** S2 · El punto de consulta es un municipio o un punto del mapa. */
    Destino,
}

/** Un punto geográfico. También es el "destino" cuando está en HomeUiState.destino. */
data class Punto(val lat: Double, val lng: Double)

object HomeMachine {

    /**
     * Distancia en km entre dos puntos (fórmula del haversine).
     *
     * Es la misma que `distanciaKm` de Home.jsx, línea 54. La Tierra se
     * asume esférica con radio 6371 km: para distancias de 5 km el error
     * respecto al elipsoide real es de centímetros, invisible aquí.
     */
    fun distKm(a: Punto, b: Punto): Double {
        val dLat = (b.lat - a.lat) * PI / 180.0
        val dLng = (b.lng - a.lng) * PI / 180.0
        val lat1 = a.lat * PI / 180.0
        val lat2 = b.lat * PI / 180.0
        val h = sin(dLat / 2) * sin(dLat / 2) +
            cos(lat1) * cos(lat2) * sin(dLng / 2) * sin(dLng / 2)
        return 2 * 6371.0 * asin(sqrt(h.coerceIn(0.0, 1.0)))
    }

    /**
     * `case 'gps'` (Home.jsx 93-127): llega una posición del watch.
     *
     *  - S0 → S1: al abrir, el GPS manda si está disponible (R3.6).
     *  - Lo guardado solo tapa la ausencia de GPS: en cuanto hay
     *    posición real, manda la real… salvo que esté a más de 5 km de
     *    la cabecera guardada, en cuyo caso sigue mandando ella (R3.4).
     *  - S2 → S1: al entrar a 5 km del destino vuelve a GPS solo; `llego`
     *    queda en true y habilita la salida (R3.1).
     *  - Ya en GPS: solo se actualiza la posición. `punto` NO se mueve:
     *    es el último punto CONSULTADO, contra el que se mide R1.a.
     */
    fun gps(estado: HomeUiState, pos: Punto): HomeUiState {
        val base = estado.copy(pos = pos, restaurado = false)

        if (estado.mode == SearchMode.Espera) {
            return base.copy(mode = SearchMode.Gps, punto = pos, llego = false)
        }

        if (estado.mode == SearchMode.Destino && estado.restaurado) {
            val destino = estado.destino
            return if (destino != null && distKm(pos, destino) > HomeUiState.RADIO_KM) {
                base.copy(mode = SearchMode.Destino, punto = destino, llego = false)
            } else {
                base.copy(mode = SearchMode.Gps, punto = pos, destino = null, llego = false)
            }
        }

        if (estado.mode == SearchMode.Destino && estado.destino != null &&
            distKm(pos, estado.destino) <= HomeUiState.RADIO_KM
        ) {
            return base.copy(mode = SearchMode.Gps, punto = pos, llego = true)
        }

        return base
    }

    /**
     * `case 'municipio'` (Home.jsx 129-153).
     *
     *  - Deseleccionar (cabecera = null): vuelve a su GPS si lo hay; si no,
     *    a espera. Sin punto no se consulta (R1.1) y además se vuelve a la
     *    portada: quitar el municipio es volver a empezar, no quedarse
     *    mirando una rejilla vacía.
     *  - Elegir: EMPIEZA a consultar (haBuscado = true).
     */
    fun municipio(estado: HomeUiState, cabecera: Cabecera?, restaurado: Boolean): HomeUiState {
        if (cabecera == null) {
            val base = estado.copy(
                destino = null,
                restaurado = false,
                llego = false,
                currentPage = 1,
                haBuscado = false,
                municipioClave = "",
            )
            val pos = estado.pos
            return if (pos != null) {
                base.copy(mode = SearchMode.Gps, punto = pos)
            } else {
                base.copy(mode = SearchMode.Espera, punto = null)
            }
        }

        val destino = Punto(cabecera.lat, cabecera.lng)
        return elegirPunto(estado, destino, restaurado)
            .copy(haBuscado = true, municipioClave = cabecera.clave)
    }

    /**
     * `case 'mapa'` (Home.jsx 155-165): mover el punto con el mapa es el
     * mismo acto que elegir municipio. NO se recuerda (R3.4 habla de la
     * ciudad elegida, no de un punto del mapa) → la clave del selector
     * se limpia.
     */
    fun mapa(estado: HomeUiState, pos: Punto): HomeUiState =
        elegirPunto(estado, pos, restaurado = false)
            .copy(haBuscado = true, municipioClave = "")

    /**
     * `case 'forzar_gps'` (Home.jsx 167-201): el botón "Mi ubicación".
     *
     * Es EXPLÍCITO: además de mover el punto, EMPIEZA a consultar
     * (haBuscado). Con un municipio elegido a más de 5 km manda la
     * CABECERA: el punto de consulta no se mueve y solo se guarda la
     * posición nueva.
     */
    fun forzarGps(estado: HomeUiState, pos: Punto?): HomeUiState {
        val p = pos ?: return estado
        val destino = estado.destino
        if (destino != null && distKm(p, destino) > HomeUiState.RADIO_KM) {
            return estado.copy(
                pos = p,
                mode = SearchMode.Destino,
                punto = destino,
                restaurado = false,
                currentPage = 1,
                haBuscado = true,
            )
        }
        return estado.copy(
            pos = p,
            mode = SearchMode.Gps,
            punto = p,
            destino = null,
            restaurado = false,
            llego = false,
            currentPage = 1,
            haBuscado = true,
        )
    }

    /**
     * `case 'mover'` (Home.jsx 203-208): refresco automático por
     * movimiento (R1.a). El throttle de 30 s vive en el ViewModel; aquí
     * solo se decide si el punto se mueve.
     */
    fun mover(estado: HomeUiState, pos: Punto): HomeUiState {
        if (estado.mode != SearchMode.Gps) return estado
        val punto = estado.punto ?: return estado
        if (distKm(pos, punto) < HomeUiState.UMBRAL_MOV_KM) return estado
        return estado.copy(punto = pos, currentPage = 1)
    }

    /**
     * `case 'reset'` (Home.jsx 210-228): salir de >5 km del destino
     * DESPUÉS de haber entrado borra TODO (R3.2), incluidos los filtros.
     * Si hay posición GPS, el propio GPS vuelve a ser el punto en el
     * mismo paso: no se deja al usuario en espera con un GPS válido sin
     * usar (R1.1, nunca navegar sin punto activo).
     */
    fun reset(estado: HomeUiState): HomeUiState {
        val base = estado.copy(
            destino = null,
            restaurado = false,
            llego = false,
            query = "",
            selectedCategory = null,
            haBuscado = false,
            currentPage = 1,
        )
        val pos = estado.pos
        return if (pos != null) {
            base.copy(mode = SearchMode.Gps, punto = pos)
        } else {
            base.copy(mode = SearchMode.Espera, punto = null)
        }
    }

    /**
     * `case 'buscar'` (Home.jsx 230-236): en cada consulta se conservan
     * texto y categoría y se vuelve a página 1. Un filtro vacío vuelve a
     * la portada (haBuscado = false) — ojo: SIN borrar lo que ya se
     * cargó, que es lo que hace la web.
     */
    fun buscar(estado: HomeUiState): HomeUiState = estado.copy(
        currentPage = 1,
        haBuscado = estado.query.isNotBlank() || estado.selectedCategory != null,
    )

    /** `case 'pagina'`: cambia de página sin tocar nada más. */
    fun pagina(estado: HomeUiState, n: Int): HomeUiState = estado.copy(currentPage = n)

    /**
     * ¿Hay que refrescar por movimiento? (efecto de Home.jsx 361-376)
     *
     * Devuelve `true` cuando hay que PROGRAMAR el refresco (con throttle)
     * y `false` en todos los demás casos. El reset lo decide el llamante.
     */
    fun refrescoPorMovimiento(estado: HomeUiState, pos: Punto): Boolean {
        if (estado.mode != SearchMode.Gps) return false
        val punto = estado.punto ?: return false
        return distKm(pos, punto) >= HomeUiState.UMBRAL_MOV_KM
    }

    /**
     * ¿Hay que hacer el RESET total? (R3.2, Home.jsx 366-371)
     * modo gps + ya llegó + destino + a más de 5 km de él.
     */
    fun necesitaReset(estado: HomeUiState, pos: Punto): Boolean {
        val destino = estado.destino ?: return false
        return estado.mode == SearchMode.Gps &&
            estado.llego &&
            distKm(pos, destino) > HomeUiState.RADIO_KM
    }

    // ───────────── helpers ─────────────

    /**
     * `elegirPuntoDeMunicipio` (Home.jsx 65-89).
     *
     *  - Si la cabecera está a 5 km o menos de tu posición es tu propio
     *    municipio: se asume y sigue en GPS — no hay nada que mover.
     *  - Si no, S0/S1 → S2: el punto pasa a ser la cabecera.
     */
    private fun elegirPunto(estado: HomeUiState, destino: Punto, restaurado: Boolean): HomeUiState {
        val pos = estado.pos
        if (pos != null && distKm(destino, pos) <= HomeUiState.RADIO_KM) {
            return estado.copy(
                destino = destino,
                mode = SearchMode.Gps,
                punto = pos,
                restaurado = false,
                llego = false,
                currentPage = 1,
            )
        }
        return estado.copy(
            destino = destino,
            mode = SearchMode.Destino,
            punto = destino,
            restaurado = restaurado,
            llego = false,
            currentPage = 1,
        )
    }

    /**
     * Punto de consulta, o null si no hay (S0).
     * Atajo para no repetir la comprobación de los dos doubles en toda
     * la UI.
     */
    fun puntoDe(estado: HomeUiState): Punto? = estado.punto
}
