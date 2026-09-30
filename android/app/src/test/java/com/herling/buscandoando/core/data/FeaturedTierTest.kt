package com.herling.buscandoando.core.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Fase 7 · pruebas de `featured_tier` -> nivel 1..4.
 *
 * ¿Por qué un test JVM y no una prueba en el emulador? Porque
 * `FeaturedTier` no toca Compose ni Android: es lógica pura sobre
 * un String. Es la regla que queremos proteger:
 *
 *   "SOLO se pinta un nivel si es exactamente '1', '2', '3' o '4'".
 *
 * El 0 de 325 negocios de producción está destacado, así que en la
 * práctica casi todo llegará como `null`. Si mañana alguien marca
 * uno con un tier heredado ('large'), este test garantiza que la app
 * muestra una tarjeta normal en vez de inventarse un color.
 */
class FeaturedTierTest {

    @Test
    fun losCuatroNivelesValidosSeConviertenASuNumero() {
        assertEquals(1, FeaturedTier.levelOf("1"))
        assertEquals(2, FeaturedTier.levelOf("2"))
        assertEquals(3, FeaturedTier.levelOf("3"))
        assertEquals(4, FeaturedTier.levelOf("4"))
    }

    @Test
    fun losTiersHeredadosDelBackendNoPintanNada() {
        // backend/businesses/views.py filtraba por 'large'/'medium'/'small'
        // antes de corregirse. Si alguno llegara, mejor no pintar.
        assertNull(FeaturedTier.levelOf("large"))
        assertNull(FeaturedTier.levelOf("medium"))
        assertNull(FeaturedTier.levelOf("small"))
    }

    @Test
    fun cualquierOtraCosaEsNull() {
        assertNull(FeaturedTier.levelOf(null))      // lo más común hoy
        assertNull(FeaturedTier.levelOf(""))        // blank del admin
        assertNull(FeaturedTier.levelOf("0"))
        assertNull(FeaturedTier.levelOf("5"))       // fuera de rango
        assertNull(FeaturedTier.levelOf(" 2"))      // con espacio
        assertNull(FeaturedTier.levelOf("nivel-2")) // formato de la web
        assertNull(FeaturedTier.levelOf("2.0"))     // decimal
        assertNull(FeaturedTier.levelOf("Nivel 2"))
    }

    @Test
    fun elOrdenDePrioridadEsDelUnoAlCuatro() {
        // El backend recorre los niveles en este orden para elegir
        // "el mejor disponible" (hasta 3 por búsqueda).
        assertEquals(listOf("1", "2", "3", "4"), FeaturedTier.VALID_TIERS)
    }
}
