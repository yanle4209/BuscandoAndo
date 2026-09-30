package com.herling.buscandoando.core.data.dto

import kotlinx.serialization.Serializable

/* ============================================================
 *  EJERCICIO — BusinessDetail
 *
 *  Rellena los XX siguiendo las MISMAS reglas de antes:
 *
 *   1. ¿Dice "= null"?       -> tipo con "?"
 *   2. ¿Trae punto decimal?  -> Double
 *   3. ¿Es arreglo []?       -> List<Tipo>
 *
 *  DIFERENCIA NUEVA:
 *   Un objeto dentro de objeto { }  ->  se convierte en OTRO data class
 *   "location": { "street": ... }   ->  val location: LocationDto?
 *
 *  El JSON real está en el chat. ¡Échale ojo!
 * ============================================================
 */


/**
 * EJERCICIO 0 — TE DÉ ESTE COMO EJEMPLO, léelo bien.
 *
 *   JSON:  "location": { "street": "Autopista Ramon Caceres #3",
 *                         "sector": "Zona urbana",
 *                         "municipality": "Moca",
 *                         "lat": 19.383738,
 *                         "full_address": "Autopista..." }
 *
 *  Nota 1: NO trae "id". Mira el JSON y no inventes campos.
 *  Nota 2: lat/lng traen decimal -> Double? (aunque igual son coordenadas)
 *  Nota 3: district y postal_code traen "" pero PODRÍAN no venir -> String?
 */
@Serializable
data class LocationDto(
    val street: String? = null,
    val sector: String? = null,
    val municipality: String? = null,
    val district: String? = null,
    val province: String? = null,
    val postal_code: String? = null,
    val country: String? = null,
    val lat: Double? = null,
    val lng: Double? = null,
    val full_address: String? = null,
)


/**
 * EJERCICIO 1 — Contacto.
 *
 *   JSON:  "contact": {
 *            "contact_person": "Ayuntamiento de Moca",
 *            "phone": "809-578-2374",
 *            "whatsapp": "",
 *            "email": "",
 *            "website": ""
 *          }
 *
 *  Escribe los 5 campos. Todos traen TEXTO en el ejemplo...
 *  ¿pero el servidor PUEDE mandar null? (¡pregúntate eso!)
 */
@Serializable
data class ContactDto(
    // EJERCICIO 1 — 5 campos aquí abajo
    val contact_person: String? = null,
    val phone: String? = null,
    val whatsapp: String? = null,
    val email: String? = null,
    val website: String? = null,


)


/**
 * EJERCICIO 2 — Horarios.
 *
 *   JSON:  "hours": [
 *            { "day": "Lunes",
 *              "open_time": "08:00:00",
 *              "close_time": "17:00:00",
 *              "is_closed": false,
 *              "is_holiday": false },
 *
 *            { "day": "Domingo",
 *              "open_time": null,        ← ¡OJO CON ESTO!
 *              "close_time": null,       ← ¡Y ESTO!
 *              "is_closed": true,
 *              "is_holiday": false }
 *          ]
 *
 *  Escribe los 5 campos.
 */
@Serializable
data class HourDto(
    // EJERCICIO 2 — 5 campos aquí abajo
    val day: String = "",
    val open_time: String? = null,
    val close_time: String? = null,
    val is_closed: Boolean = false,
    val is_holiday: Boolean = false,

)


/**
 * EJERCICIO 3 — El objeto raíz de GET /api/businesses/<slug>/
 *
 *  Compara con tu Business de la lista:
 *    - AHORA SÍ trae: description, publication_status, updated_at
 *    - AHORA NO trae: street, municipality, phone, whatsapp, email...
 *                      (esos están DENTRO de location/contact)
 *    - SÍ trae: latitude/longitude "aplanados" (el serializer los duplica)
 *
 *  Campos YA escritos para que te guíes. Completa los XX.
 */
@Serializable
data class BusinessDetail(
    // ----- Identidad -----
    val id: Int = 0,
    val name: String = "",
    val slug: String = "",

    val description: String? = null,          // "estadio de futbol."
    val short_description: String? = null,

    // ----- Categoria -----
    val category: Int = 0,
    val category_name: String? = null,
    val category_icon: String? = null,

    // ----- Publicacion (NUEVO respecto a la lista) -----
    val publication_status: Int = 0,      // JSON: 2  → número entero
    val publication_status_name: String? = null,  // "Publicado"

    // ----- Estados -----
    val operational_status: Int = 1,      // JSON: 1 → número entero
    val operational_status_name: String? = null,
    val operational_status_color: String? = null,   // "#22c55e"
    val effective_status: String? = null,
    val effective_status_name: String? = null,

    // ----- Destacado -----
    val is_featured: Boolean? = null,          // false  y también null
    val featured_tier: String? = null,

    // ----- Ubicacion aplanada (el serializer la DUPLICA) -----
    val latitude: Double? = null,             // 19.383738
    val longitude: Double? = null,            // -70.534247

    // ----- Los 3 objetos ANIDADOS -----
    val location: LocationDto? = null,             // { ... }   → LocationDto?
    val contact: ContactDto? = null,              // { ... }   → ContactDto?
    val hours: List<HourDto> = emptyList(),         // [ {...} ] → List<HourDto>
    val images: List<ImageDto> = emptyList(),

    // ----- Fechas (NUEVO: updated_at) -----
    val created_at: String? = null,
    val updated_at: String? = null,
)
