package com.herling.buscandoando.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log

/**
 * Acciones ACCIONABLES de la tarjeta y de la ficha.
 *
 * Es la contraparte de los `<a href>` de la web:
 *
 *   href="tel:809…"          -> telefono(context, "809-…")
 *   href="https://wa.me/…"   -> whatsapp(context, "809-…")
 *   href="mailto:…"          -> correo(context, "…")
 *   href="…google.com/maps"  -> mapa(context, lat, lng)
 *
 * La web navega sola; Android necesita un Intent. Si no hay app que
 * atienda la URL (sin WhatsApp, sin navegador) `runCatching` se traga
 * la ActivityNotFoundException: peor es que la app se cueste al tocar
 * un teléfono.
 */
object Acciones {

    /** Abre cualquier URL con la app que corresponda. */
    fun abrir(context: Context, url: String) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        runCatching { context.startActivity(intent) }
            .onFailure {
                Log.w("BuscandoAndo", "No hay app para $url: ${it::class.simpleName}")
            }
    }

    /** Llama (marcador con el número ya puesto, sin marcar solas). */
    fun telefono(context: Context, numero: String) =
        abrir(context, "tel:${numero.trim()}")

    /** Abre la conversación de WhatsApp. Solo dígitos, como en la web. */
    fun whatsapp(context: Context, numero: String) =
        abrir(context, "https://wa.me/${numero.filter { it.isDigit() }}")

    /** Google Maps en el punto exacto del negocio. */
    fun mapa(context: Context, lat: Double, lng: Double) =
        abrir(context, "https://www.google.com/maps?q=$lat,$lng")

    /** Cliente de correo con la dirección ya escrita. */
    fun correo(context: Context, email: String) =
        abrir(context, "mailto:${email.trim()}")

    /** Web del negocio (con esquema si no lo trae). */
    fun web(context: Context, url: String) {
        val limpia = url.trim()
        abrir(context, if (limpia.startsWith("http")) limpia else "https://$limpia")
    }
}
