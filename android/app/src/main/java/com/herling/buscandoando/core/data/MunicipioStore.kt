package com.herling.buscandoando.core.data

import android.annotation.SuppressLint
import android.content.Context
import android.content.SharedPreferences
import com.herling.buscandoando.core.data.dto.Cabecera
import kotlinx.serialization.json.Json

/**
 * R3.4 · El municipio elegido se RECUERDA entre sesiones.
 *
 * Es el equivalente Android de:
 *
 *   localStorage.setItem('buscandoando.municipio', JSON.stringify(c))
 *   localStorage.getItem('buscandoando.municipio')
 *
 * Se guarda el JSON completo de la cabecera (no solo la clave) porque
 * al restaurar hacen falta también lat y lng: sin coordenadas no hay
 * círculo de 5 km que trazar.
 *
 * ── ¿Por qué un object y no una clase inyectada? ──────────────────
 *
 * Mismo motivo que `ApiClient`: una sola instancia compartida y cero
 * cableado. `init()` se llama desde MainActivity.onCreate(), ANTES de
 * que exista ningún ViewModel, así que `prefs` nunca está vacío.
 */
object MunicipioStore {

    /** Mismo nombre de clave que en la web (rastro de depuración). */
    private const val PREFS = "buscandoando"

    private const val CLAVE_MUNICIPIO = "municipio"

    private val json = Json { ignoreUnknownKeys = true }

    private var prefs: SharedPreferences? = null

    /** Se llama una vez, al arrancar la Activity. Idempotente. */
    fun init(context: Context) {
        if (prefs == null) {
            prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        }
    }

    /**
     * Guarda la cabecera elegida a mano.
     *
     * ⚠️ El destino que viene del mapa NO se guarda: R3.4 habla de la
     * ciudad elegida, no de un punto suelto (Home.jsx elegirPuntoDelMapa).
     */
    fun guardar(cabecera: Cabecera) {
        prefs?.edit()
            ?.putString(CLAVE_MUNICIPIO, json.encodeToString(Cabecera.serializer(), cabecera))
            ?.apply()
    }

    /**
     * Devuelve la cabecera guardada, o null si no la hay / está corrupta.
     *
     * Corrompido = modo privado, borrado de datos o un JSON a medias:
     * se queda en portada y el usuario elige municipio a mano (mismo
     * `catch` silencioso que restaurarMunicipio en Home.jsx).
     */
    fun leer(): Cabecera? {
        val bruto = prefs?.getString(CLAVE_MUNICIPIO, null) ?: return null
        return try {
            json.decodeFromString(Cabecera.serializer(), bruto)
                .takeIf { it.municipio.isNotBlank() && !(it.lat == 0.0 && it.lng == 0.0) }
        } catch (e: Exception) {
            null
        }
    }

    /** El usuario quitó el municipio: no se restaura en la próxima sesión. */
    fun borrar() {
        prefs?.edit()?.remove(CLAVE_MUNICIPIO)?.apply()
    }

    /** Visible para tests: deja el almacén limpio. */
    @SuppressLint("ApplySharedPref")
    fun limpiarParaTestes() {
        prefs?.edit()?.clear()?.commit()
    }
}
