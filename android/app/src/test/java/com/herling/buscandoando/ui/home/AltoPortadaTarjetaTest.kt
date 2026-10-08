package com.herling.buscandoando.ui.home

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Tests del alto de la portada de las tarjetas (ver [altoPortadaTarjeta]).
 *
 * Por qué existen: es la regla que hace que la tarjeta deje de verse
 * "aplastada" en el móvil —la foto era una tira de 108dp sobre una
 * tarjeta de ancho completo— y que quede casi cuadrada, como la de la
 * web. Si alguien cambia el 50% por otro número, aquí se entera antes
 * que en el móvil de Herling.
 */
class AltoPortadaTarjetaTest {

    @Test
    fun `la portada ocupa la mitad del ancho de la tarjeta`() {
        // Móvil: celda de UNA columna (pantalla menos los dos
        // márgenes de 14dp). Sale una foto de ~165-175dp.
        assertEquals(166.dp, altoPortadaTarjeta(332.dp))
        assertEquals(175.dp, altoPortadaTarjeta(350.dp))
        // Tablet: celda de TRES columnas (mismo corte de 600dp).
        assertEquals(124.dp, altoPortadaTarjeta(248.dp))
    }

    @Test
    fun `sin ancho acotado la portada vuelve al alto de siempre`() {
        // No ocurre en la práctica (las tarjetas siempre están en una
        // celda o en un ancho conocido), pero si el ancho llegara sin
        // acotar no queremos dibujar una portada de altura infinita.
        assertEquals(108.dp, altoPortadaTarjeta(Float.POSITIVE_INFINITY.dp))
    }
}
