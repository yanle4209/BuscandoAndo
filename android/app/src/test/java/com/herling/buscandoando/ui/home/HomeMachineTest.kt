package com.herling.buscandoando.ui.home

import com.herling.buscandoando.core.data.dto.Cabecera
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests de la máquina de estados: el `reducer` de Home.jsx trasladado a
 * Kotlin (ver HomeMachine.kt).
 *
 * Por qué son VALIOSOS aquí: es la única pieza de la Fase 8 que no se
 * puede ver sin un dispositivo. Cada test es una regla de R1.x/R3.x
 * comprobada de verdad: si alguien toca el umbral de 500 m, el radio
 * de 5 km o el orden de las transiciones, estos tests fallan en CI y
 * no en el móvil de Herling.
 *
 * Coordenadas de trabajo:
 *   MOCA   = el centro de Moca (de donde parte el GPS)
 *   CERCA  ≈ 1,1 km al norte (dentro del radio)
 *   LEJOS  ≈ 11,1 km al norte (fuera del radio)
 *   MOVER  ≈   550 m al norte (justo sobre el umbral de R1.a)
 */
class HomeMachineTest {

    private companion object {
        val MOCA = Punto(19.4800, -70.9200)
        val CERCA = Punto(19.4900, -70.9200)   // ~1,1 km
        val MOVER = Punto(19.4850, -70.9200)   // ~550 m
        val LEJOS = Punto(19.5800, -70.9200)   // ~11,1 km

        val CABECERA_MOCA = Cabecera("Espaillat", "Moca", 19.4800, -70.9200)
        val CABECERA_LEJOS = Cabecera("Santiago", "Villa González", 19.5300, -70.9200)

        /** Estado inicial: portada, sin nada. */
        fun inicial() = HomeUiState()
    }

    // ───────────────────── distancia ─────────────────────

    @Test
    fun `distKm entre el mismo punto es cero`() {
        assertEquals(0.0, HomeMachine.distKm(MOCA, MOCA), 0.0001)
    }

    @Test
    fun `distKm es simétrica y respeta la escala`() {
        val a = HomeMachine.distKm(MOCA, MOVER)
        val b = HomeMachine.distKm(MOVER, MOCA)
        assertEquals(a, b, 0.0001)
        assertTrue("esperaba ~0,55 km y dio $a", a > 0.5 && a < 0.6)
    }

    // ───────────────────── S0 → S1 (GPS) ─────────────────────

    @Test
    fun `el primer fix sale de espera a gps y mueve el punto`() {
        val estado = HomeMachine.gps(inicial(), MOCA)

        assertEquals(SearchMode.Gps, estado.mode)
        assertEquals(MOCA, estado.punto)
        assertEquals(MOCA, estado.pos)
    }

    @Test
    fun `el primer fix NO empieza a buscar (la portada sigue)`() {
        // R1.1 / paridad con la web: el GPS da punto, pero el usuario
        // todavía no ha hecho nada explícito.
        val estado = HomeMachine.gps(inicial(), MOCA)

        assertFalse(estado.haBuscado)
        assertEquals(SearchMode.Gps, estado.mode)
    }

    @Test
    fun `estar en gps no mueve el punto consultado al andar`() {
        val conPunto = HomeMachine.gps(inicial(), MOVER)

        // El punto sigue siendo el último CONSULTADO; mover() (R1.a) es
        // quien lo actualiza, nunca el simple hecho de recibir un fix.
        assertEquals(MOVER, conPunto.punto)
        assertEquals(MOVER, conPunto.pos)
    }

    // ───────────────────── S0/S1 → S2 (municipio) ─────────────────────

    @Test
    fun `elegir municipio lejano pasa a destino y EMPIEZA a buscar`() {
        val estado = HomeMachine.municipio(inicial(), CABECERA_LEJOS, restaurado = false)

        assertEquals(SearchMode.Destino, estado.mode)
        assertEquals(Punto(19.5300, -70.9200), estado.destino)
        assertEquals(Punto(19.5300, -70.9200), estado.punto)
        assertTrue(estado.haBuscado)
        assertEquals("Santiago~Villa González", estado.municipioClave)
        assertFalse(estado.llego)
    }

    @Test
    fun `elegir municipio a menos de 5 km sigue en gps con tu posicion`() {
        val conGps = HomeMachine.gps(inicial(), MOCA)
        val estado = HomeMachine.municipio(conGps, CABECERA_MOCA, restaurado = false)

        assertEquals(SearchMode.Gps, estado.mode)
        assertEquals(MOCA, estado.punto)
        assertTrue(estado.haBuscado)
    }

    @Test
    fun `quitar el municipio vuelve a tu posicion si la hay`() {
        val estado = HomeMachine.municipio(
            HomeMachine.gps(inicial(), MOCA),
            cabecera = null,
            restaurado = false,
        )

        assertEquals(SearchMode.Gps, estado.mode)
        assertEquals(MOCA, estado.punto)
        assertFalse(estado.haBuscado)   // volver a empezar = portada
        assertNull(estado.destino)
        assertEquals("", estado.municipioClave)
    }

    @Test
    fun `quitar el municipio sin posicion deja espera y sin punto`() {
        val estado = HomeMachine.municipio(inicial(), CABECERA_MOCA, restaurado = false)
        val limpio = HomeMachine.municipio(estado, cabecera = null, restaurado = false)

        assertEquals(SearchMode.Espera, limpio.mode)
        assertNull(limpio.punto)
        assertFalse(limpio.haBuscado)
    }

    @Test
    fun `elegir municipio conserva el texto escrito pero baja a pagina 1`() {
        val escrito = inicial().copy(query = "pan", currentPage = 4)
        val estado = HomeMachine.municipio(escrito, CABECERA_LEJOS, restaurado = false)

        assertEquals("pan", estado.query)
        assertEquals(1, estado.currentPage)
    }

    // ───────────────────── R3.4 · destino restaurado ─────────────────────

    @Test
    fun `el municipio guardado se queda si el gps esta lejos`() {
        val conPos = HomeMachine.gps(inicial(), LEJOS)
        val restaurado = HomeMachine.municipio(conPos, CABECERA_MOCA, restaurado = true)

        val conFix = HomeMachine.gps(restaurado, LEJOS)

        assertEquals(SearchMode.Destino, conFix.mode)
        assertEquals(Punto(19.4800, -70.9200), conFix.punto)  // manda el guardado
        assertFalse(conFix.restaurado)                          // ya no es "restaurado"
        assertTrue(conFix.haBuscado)
    }

    @Test
    fun `cerca del municipio guardado se asume que es el tuyo y vuelves a gps`() {
        val conPos = HomeMachine.gps(inicial(), LEJOS)
        val restaurado = HomeMachine.municipio(conPos, CABECERA_MOCA, restaurado = true)

        // El usuario llega a Moca: el guardado ya no tapa nada.
        val conFix = HomeMachine.gps(restaurado, MOCA)

        assertEquals(SearchMode.Gps, conFix.mode)
        assertEquals(MOCA, conFix.punto)
        assertNull(conFix.destino)
    }

    // ───────────────────── R3.1 / R3.2 · llegada y salida ─────────────────────

    @Test
    fun `entrar a 5 km del destino pasa a gps y marca llego`() {
        val enDestino = HomeMachine.municipio(inicial(), CABECERA_MOCA, restaurado = false)
        val conFix = HomeMachine.gps(enDestino, CERCA)

        assertEquals(SearchMode.Gps, conFix.mode)
        assertEquals(CERCA, conFix.punto)
        assertTrue(conFix.llego)
        assertEquals(CABECERA_MOCA.let { Punto(it.lat, it.lng) }, conFix.destino)
    }

    @Test
    fun `salir a mas de 5 km de un destino alcanzado dispara el reset`() {
        val llegada = HomeMachine.gps(
            HomeMachine.municipio(inicial(), CABECERA_MOCA, restaurado = false),
            CERCA,
        )
        assertTrue(HomeMachine.necesitaReset(llegada, LEJOS))
        assertFalse(HomeMachine.necesitaReset(llegada, MOVER))
    }

    @Test
    fun `el reset borra destino filtros y vuelve a portada`() {
        val buscado = inicial().copy(
            query = "pan",
            currentPage = 3,
        )
        val llegada = HomeMachine.gps(
            HomeMachine.municipio(buscado, CABECERA_MOCA, restaurado = false),
            CERCA,
        )
        val trasReset = HomeMachine.reset(llegada)

        assertNull(trasReset.destino)
        // Con posición GPS, el PRÓPIO GPS vuelve a ser el punto en el
        // mismo paso (R1.1): no se deja al usuario sin punto activo.
        assertEquals(CERCA, trasReset.punto)
        assertEquals(SearchMode.Gps, trasReset.mode)
        assertFalse(trasReset.llego)
        assertEquals("", trasReset.query)       // R3.2: filtros en cero
        assertEquals(1, trasReset.currentPage)
        assertFalse(trasReset.haBuscado)        // ...y otra vez portada
    }

    @Test
    fun `sin posicion el reset deja espera y sin punto`() {
        val llegada = HomeMachine.municipio(inicial(), CABECERA_MOCA, restaurado = false)
        val conPos = HomeMachine.gps(llegada, CERCA)
        val sinPos = conPos.copy(pos = null)

        val trasReset = HomeMachine.reset(sinPos)

        assertEquals(SearchMode.Espera, trasReset.mode)
        assertNull(trasReset.punto)
    }

    // ───────────────────── R1.a · refresco por movimiento ─────────────────────

    @Test
    fun `no se refresca si te mueves menos de 500 m`() {
        val estado = HomeMachine.gps(inicial(), MOCA)
        val despues = HomeMachine.gps(estado, MOCA.copy(lat = MOCA.lat + 0.003)) // ~330 m

        assertFalse(HomeMachine.refrescoPorMovimiento(despues, despues.pos!!))
    }

    @Test
    fun `si te alejas 500 m del punto consultado toca refrescar`() {
        val estado = HomeMachine.gps(inicial(), MOCA)

        assertTrue(HomeMachine.refrescoPorMovimiento(estado, MOVER))
        // mover() lleva el punto de consulta a la posición nueva...
        assertEquals(MOVER, HomeMachine.mover(estado, MOVER).punto)
        assertEquals(1, HomeMachine.mover(estado, MOVER).currentPage)
    }

    @Test
    fun `mover no hace nada en modo destino`() {
        val estado = HomeMachine.municipio(inicial(), CABECERA_LEJOS, restaurado = false)
        val desplazado = HomeMachine.mover(estado, MOCA)

        assertEquals(estado.punto, desplazado.punto)
    }

    @Test
    fun `sin punto activo no hay refresco`() {
        assertFalse(HomeMachine.refrescoPorMovimiento(inicial(), MOCA))
    }

    // ───────────────────── forzar_gps ─────────────────────

    @Test
    fun `el boton mi ubicacion empieza a buscar y usa tu posicion`() {
        val estado = HomeMachine.forzarGps(inicial(), MOCA)

        assertEquals(SearchMode.Gps, estado.mode)
        assertEquals(MOCA, estado.punto)
        assertTrue(estado.haBuscado)
        assertEquals(MOCA, estado.pos)
    }

    @Test
    fun `con un municipio lejano elegido mi ubicacion no mueve el punto`() {
        val enDestino = HomeMachine.municipio(inicial(), CABECERA_LEJOS, restaurado = false)
        val estado = HomeMachine.forzarGps(enDestino, MOCA)

        assertEquals(SearchMode.Destino, estado.mode)
        assertEquals(Punto(19.5300, -70.9200), estado.punto)  // manda el municipio
        assertEquals(MOCA, estado.pos)                         // pero sí se guarda dónde estás
        assertTrue(estado.haBuscado)
    }

    // ───────────────────── buscar (haBuscado) ─────────────────────

    @Test
    fun `buscar con texto activa la consulta y vuelve a la pagina 1`() {
        val estado = HomeMachine.buscar(inicial().copy(query = "hotel", currentPage = 5))

        assertTrue(estado.haBuscado)
        assertEquals(1, estado.currentPage)
    }

    @Test
    fun `buscar con todo vacio vuelve a portada sin tocar el texto`() {
        val estado = HomeMachine.buscar(inicial().copy(query = "  ", currentPage = 5))

        assertFalse(estado.haBuscado)
        assertEquals(1, estado.currentPage)
    }

    // ───────────────────── mapa ─────────────────────

    @Test
    fun `tocar el mapa busca y limpia el municipio del selector`() {
        val estado = HomeMachine.mapa(inicial(), MOVER)

        assertEquals(SearchMode.Destino, estado.mode)
        assertEquals(MOVER, estado.punto)
        assertTrue(estado.haBuscado)
        assertEquals("", estado.municipioClave)  // un punto no es un municipio
    }
}
