package com.herling.buscandoando.core.network

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Los tiempos de red de [ApiClient] frente al servidor DORMIDO.
 *
 * Por qué existen: Render apaga la instancia gratis tras ~15 min sin
 * peticiones y el arranque en frío tarda 30-50 s — mientras tanto la
 * petición queda esperando y responde al terminar. Con los defaults de
 * OkHttp (10 s) la app se rendía ANTES que el servidor y enseñaba un
 * error de red justo cuando lo que pasaba era que se estaba
 * despertando. Si alguien devuelve los tiempos a 10 s, aquí se entera.
 */
class TimeoutRedTest {

    @Test
    fun `la lectura aguanta el arranque en frio de Render`() {
        // 30-50 s de Render + margen: por debajo de 60 no sirve.
        assertTrue(ApiClient.TIMEOUT_LECTURA_S >= 60)
    }

    @Test
    fun `la conexion tampoco es el default de OkHttp`() {
        // El connect por defecto son 10 s; le damos el doble.
        assertTrue(ApiClient.TIMEOUT_CONEXION_S >= 20)
    }
}
