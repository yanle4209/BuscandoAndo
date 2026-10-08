package com.herling.buscandoando.core.network

import com.herling.buscandoando.BuildConfig
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
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

    /**
     * Tiempos de red pensados para un servidor que DUERME.
     *
     * Render apaga la instancia gratis tras ~15 min sin peticiones y
     * el PRIMER arranque en frío tarda 30-50 s. La petición que llega
     * mientras despierta queda esperando y responde al terminar, pero
     * solo si los tiempos la dejan: con los defaults de OkHttp (10 s
     * de lectura) la app se rendía ANTES que el servidor y enseñaba
     * un error de red justo cuando lo que pasaba era que la instancia
     * se estaba despertando.
     *
     * No hace falta "despertar" el servidor aparte ni abrir la URL en
     * el navegador: el `init` del HomeViewModel ya dispara
     * loadCategories() + loadCabeceras() al abrir la app, y web y API
     * son la MISMA instancia de Render — cualquier petición la arranca.
     */
    internal const val TIMEOUT_CONEXION_S = 30L
    internal const val TIMEOUT_LECTURA_S = 90L
    internal const val TIMEOUT_ESCRITURA_S = 30L

    /** Cliente con esos tiempos (el de OkHttp por defecto se rinde a los 10 s). */
    private val http = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_CONEXION_S, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_LECTURA_S, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_ESCRITURA_S, TimeUnit.SECONDS)
        .build()

    private val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)                       // DEBE terminar en "/"
        .client(http)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    /**
     * La instancia que usara toda la app.
     * Retrofit implementa BuscandoAndoApi en tiempo de ejecucion
     * (reflection) — tu nunca ves el codigo HTTP.
     */
    val api: BuscandoAndoApi = retrofit.create(BuscandoAndoApi::class.java)
}
