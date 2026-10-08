package com.herling.buscandoando.ui.home

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Tests del corte de columnas de la rejilla (ver [columnasDeRejilla]).
 *
 * Por qué existen: es la ÚNICA regla de esta pantalla que no se puede
 * comprobar sin un dispositivo de cada tamaño (teléfono y tablet). Si
 * alguien mueve el umbral de 600dp, aquí se entera antes que en el
 * móvil de Herling.
 */
class ColumnasRejillaTest {

    @Test
    fun `una ventana de movil va de una columna`() {
        // Retrato de teléfono normal, estrecho y ancho, y justo por
        // debajo del corte.
        assertEquals(1, columnasDeRejilla(360.dp))
        assertEquals(1, columnasDeRejilla(411.dp))
        assertEquals(1, columnasDeRejilla(599.dp))
    }

    @Test
    fun `una ventana de tablet va a tres columnas`() {
        // Justo en el corte (tabla de 7") y las de siempre.
        assertEquals(3, columnasDeRejilla(600.dp))
        assertEquals(3, columnasDeRejilla(800.dp))
        assertEquals(3, columnasDeRejilla(1280.dp))
    }
}
