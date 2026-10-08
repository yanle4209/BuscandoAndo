package com.herling.buscandoando.core.data.dto

import kotlinx.serialization.Serializable

/* ============================================================
 *  EJERCICIO — Rellena los huecos marcados con  XX
 *
 *  REGLAS DE ORO:
 *   1. JSON número entero       -> Int
 *   2. JSON número con decimal  -> Double
 *   3. JSON texto ("...")       -> String
 *   4. JSON true/false          -> Boolean
 *   5. JSON arreglo []          -> List<Tipo>
 *   6. SIEMPRE puede venir null -> Tipo?   (y ponerle " = null")
 *
 *  El JSON de referencia está en el chat de arriba.
 * ============================================================
 */

/** GET /api/categories/  ->  results[] */
@Serializable
data class Category(
    val id: Int = 0,
    val name: String = "",
    val slug: String = "",
    val icon: String = "",
    val description: String? = null,
)

/**
 * Envolvemos CUALQUIER respuesta paginada de Django REST.
 * Siempre trae: { count, next, previous, results }
 *
 *  EJERCICIO 1 — escribe los 4 tipos:
 */
@Serializable
data class PagedResponse<T>(
    val count: Int = 0,           // pista: número entero
    val next: String? = null,         // pista: trae una URL o null
    val previous: String? = null,     // pista: igual que next
    val results: List<T> = emptyList(),  // pista: arreglo de T
)

/** Un elemento del arreglo "images" */
@Serializable
data class ImageDto(
    val id: Int = 0,
    val image: String? = null,
    val image_url: String? = null,
    val caption: String? = null,
    val order: Int? = null,
)

/**
 * GET /api/businesses/  ->  results[]
 *
 *  EJERCICIO 2 — completa los campos marcados con XX.
 *  CUIDADO: mira bien si el JSON trae null o no.
 */
@Serializable
data class Business(
    // ----- Identidad -----
    val id: Int = 0,
    val name: String = "",
    val slug: String? = null,           // "estadio-jose-maria-hidalgo-san"
                                        //  (clave para abrir el DETALLE)

    val short_description: String? = null,   // JSON: "Estadio de futbol."  y  ""

    // ----- Categoria -----
    val category: Int = 0,
    val category_name: String? = null,       // JSON: "Deporte"
    val category_icon: String? = null,       // JSON: "football"  (Lucide)

    // ----- Estados (el API trae DOS variantes) -----
    val effective_status: String? = null,    // JSON: "abierto"
    val effective_status_name: String? = null, // JSON: "Abierto"

    // ----- Destacado -----
    val is_featured: Boolean? = null,         // JSON: false   y  puede venir null
    val featured_tier: String? = null,       // JSON: null

    // ----- Ubicacion -----
    val latitude: Double? = null,            // JSON: 19.383738  y  null
    val longitude: Double? = null,           // JSON: -70.534247 y  null

    val municipality: String? = null,
    val province: String? = null,
    val street: String? = null,             // JSON: "Calle Duarte #12" o null

    // ----- Contacto (mira bien: "809-578-2374" y también null) -----
    val phone: String? = null,
    val whatsapp: String? = null,           // el mismo número, o null
    val email: String? = null,              // "ayuntamiento@moca.go.do"
    val contact_person: String? = null,      // JSON: "Ayuntamiento de Moca" y también null

    // ----- Multimedia -----
    val images: List<ImageDto> = emptyList(),       // JSON: [ {..}, {..} ]

    // ----- Fechas -----
    val created_at: String? = null,          // JSON: "2026-09-20T17:36:04.256000-05:00"
)

/**
 * POST /api/corrections/ — lo que manda el botón "Corregir".
 *
 * Mismos tres campos que CorrectionCreateSerializer (backend):
 * `business` (PK), `campo` (una de las 8 opciones de Correction.CAMPOS)
 * y `mensaje` (mínimo 10 caracteres, lo comprueba el backend).
 *
 * Es público: no lleva login ni token, igual que el formulario de la web.
 */
@Serializable
data class CorrectionPayload(
    val business: Int,
    val campo: String,
    val mensaje: String,
)

/**
 * El 201 que devuelve el backend.
 *
 * Todos los campos llevan valor por defecto: a la app solo le importa
 * que la respuesta sea 201, no el contenido del aviso (eso es cosa
 * del admin). Con defaults cabemos ante cualquier cambio del
 * serializer sin romper la app.
 */
@Serializable
data class CorrectionCreada(
    val id: Int = 0,
    val business: Int = 0,
    val campo: String = "",
    val mensaje: String = "",
    val estado: String = "pendiente",
    val created_at: String? = null,
)
