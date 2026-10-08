package com.herling.buscandoando.core.data.dto

import kotlinx.serialization.Serializable

/**
 * Cabecera municipal: el centro de uno de los 158 municipios.
 *
 * Es el "destino" que se puede elegir en el selector de la web
 * (`<select class="municipio-group">` de SearchBar.jsx) y que la
 * máquina de estados guarda como `destino`.
 *
 *   React                         Kotlin
 *   ───────────────────────────   ─────────────────────────────
 *   { provincia, municipio,       Cabecera(provincia, municipio,
 *     lat, lng }                     lat, lng)
 *
 * `ignoreUnknownKeys` del ApiClient ya nos blindaría contra campos
 * extra, pero declara-los todos hace que el DTO documente el contrato.
 */
@Serializable
data class Cabecera(
    val provincia: String = "",
    val municipio: String = "",
    val lat: Double = 0.0,
    val lng: Double = 0.0,
) {
    /**
     * Clave estable "Provincia~Municipio".
     *
     * Espejo EXACTO de `claveCabecera` (frontend/src/municipios.js):
     * dos provincias pueden tener municipios con el mismo nombre, así
     * que la provincia entra en la clave. Se usa como identidad dentro
     * del selector y como valor guardado en disco.
     */
    val clave: String get() = "$provincia~$municipio"
}
