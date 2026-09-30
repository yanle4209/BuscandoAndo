package com.herling.buscandoando.core.network

import com.herling.buscandoando.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Configuracion de red — el equivalente a un axios.create() en React.
 *
 *   React                          Kotlin
 *   ────────────────────────────   ────────────────────────────
 *   axios.create({ baseURL, ... }) Retrofit.Builder().baseUrl(...)
 *   response.data                  response.body()  (que ya es tu data class)
 *   JSON.parse(res)                kotlinx.serialization lo hace solo
 *
 *  object = SINGLETON. Solo existe UNA instancia de ApiClient en toda la app
 *  (igual que un "export const api" en JS: un solo objeto compartido).
 */
object ApiClient {

    /**
     * La URL la inyecta Gradle en `build.gradle.kts` (BuildConfig),
     * no está escrita aquí: así producción / backend local se eligen
     * al compilar y no hace falta editar este archivo.
     */
    private val BASE_URL = BuildConfig.API_BASE_URL

    /**
     * Configuracion del traductor JSON.
     *
     *  ignoreUnknownKeys = true  ->  LA LINEA MAS IMPORTANTE DE ESTE ARCHIVO.
     *
     *  Tu DTO [com.herling.buscandoando.core.data.dto.Business] NO declara
     *  todos los campos que manda el servidor (ej: slug, street,
     *  operational_status_color, category_icon...).
     *
     *  Sin esto, kotlinx.serialization tira:
     *      SerializationException: Encountered an unknown key 'street'
     *  y la app CRASHEA.
     *
     *  Con esto, simplemente ignora lo que no reconoce.
     *
     *  > Analogia TS: es como tipar con `{ name: string }` cuando el objeto
     *    real trae 30 campos. TS no se queja de los extras.
     */
    private val json = Json {
        ignoreUnknownKeys = true   // ignora campos que tu DTO no declara
        isLenient = true           // acepta comillas simples, etc.
        coerceInputValues = true   // null -> valor por defecto si el tipo no lo admite
        explicitNulls = false      // no exige los campos null del JSON
    }

    private val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)                       // DEBE terminar en "/"
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    /**
     * La instancia que usara toda la app.
     * Retrofit implementa BuscandoAndoApi en tiempo de ejecucion
     * (reflection) — tu nunca ves el codigo HTTP.
     */
    val api: BuscandoAndoApi = retrofit.create(BuscandoAndoApi::class.java)
}
