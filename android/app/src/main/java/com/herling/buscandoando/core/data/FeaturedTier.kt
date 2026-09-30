package com.herling.buscandoando.core.data

/**
 * FASE 7 · Niveles de destacado.
 *
 * El backend define los niveles en `Business.FEATURED_TIERS`
 * (backend/businesses/models.py):
 *
 *     ('1', 'Nivel 1 - Principal')  ->  oro      #B3B334
 *     ('2', 'Nivel 2 - Alto')       ->  plata    #A0A0A0
 *     ('3', 'Nivel 3 - Medio')      ->  bronce   #CD7F32
 *     ('4', 'Nivel 4 - Basico')     ->  marrón   #8B7355
 *
 * ⚠️ Son CADENAS "1".."4", NO números. Y el campo llega como
 * `String?`: hoy 0 de 325 negocios están destacados, así que en
 * la práctica casi siempre es `null`.
 *
 * Por eso `levelOf` es a prueba de datos raros:
 *
 *   "2"    -> 2          ✅ se pinta la pastilla "Nivel 2"
 *   null   -> null       ✅ tarjeta normal (lo usual)
 *   ""     -> null       ✅ tarjeta normal
 *   "large"-> null       ⚠️ tier HEREDADO de una versión antigua del
 *                           backend: mejor no pintar nada que pintar
 *                           un nivel inventado.
 *
 * Esta clase no toca Compose a propósito: así se puede probar con un
 * test JVM normal (sin emulador). Los COLORES viven en la capa UI.
 */
object FeaturedTier {

    /** Niveles válidos, del mejor (1) al peor (4). */
    val VALID_TIERS = listOf("1", "2", "3", "4")

    /**
     * Convierte el `featured_tier` del API en un nivel 1..4.
     *
     * @return 1..4 si es un nivel válido, o `null` si no hay que
     *         pintar nada.
     */
    fun levelOf(tier: String?): Int? =
        tier?.takeIf { it in VALID_TIERS }?.toInt()
}
