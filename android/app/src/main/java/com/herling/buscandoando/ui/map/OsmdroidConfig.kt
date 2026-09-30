package com.herling.buscandoando.ui.map

import android.content.Context
import java.io.File
import org.osmdroid.config.Configuration

/**
 * FASE 5 — Configuración de osmdroid.
 *
 * Debe ejecutarse ANTES de crear el primer `MapView`; si no, el mapa
 * nace con los valores por defecto y hay que recrearlo.
 *
 * ── ¿Por qué hacen falta estas 3 líneas? ─────────────────────────
 *
 * 1. userAgentValue
 *    OpenStreetMap exige identificar QUIÉN baja sus teselas
 *    (política de uso de tile.openstreetmap.org). Sin un userAgent
 *    reconocible te pueden bloquear la IP. Tu app se presenta con su
 *    package name, que es el mínimo aceptable.
 *
 * 2/3. Rutas de la caché
 *      Por defecto osmdroid apunta al almacenamiento EXTERNO
 *      compartido (`Environment.getExternalStorageDirectory()`), que
 *      desde Android 10 está restringido y pediría permisos.
 *
 *      Apuntando al almacenamiento INTERNO de la app
 *      (`filesDir` / `cacheDir`) NO necesitamos NINGÚN permiso de
 *      almacenamiento: es privado, siempre escribible y se limpia
 *      si el usuario borra los datos.
 *
 * Equivalente "web": es como declarar el `User-Agent` de fetch() y
 * elegir dónde guardar el Service Worker Cache.
 */
fun initOsmdroid(context: Context) {
    // Usamos los setters explícitos (métodos Java) en lugar de la
    // sintaxis de propiedad: IConfigurationProvider declara además un
    // `getOsmdroidBasePath(Context)` sobrecargado, y eso puede
    // confundir al sintetizador de propiedades de Kotlin.
    val config = Configuration.getInstance()
    config.setUserAgentValue(context.packageName)
    config.setOsmdroidBasePath(context.filesDir)
    config.setOsmdroidTileCache(File(context.cacheDir, "osmdroid_tiles"))
}
