package com.herling.buscandoando.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.ContentCut
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.Handyman
import androidx.compose.material.icons.filled.HealthAndSafety
import androidx.compose.material.icons.filled.Hotel
import androidx.compose.material.icons.filled.Laptop
import androidx.compose.material.icons.filled.LocalHospital
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Restaurant
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.filled.SportsSoccer
import androidx.compose.material.icons.filled.Storefront
import androidx.compose.material.icons.filled.Work
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Puente entre los íconos de TU BASE DE DATOS (Lucide, de la web)
 * y los Material Icons de Android.
 *
 * Tu BD guarda cadenas como "stethoscope" o "football". Ese es el
 * "nombre de contrato" que NUNCA cambia. Si mañana cambias la web a
 * otro set de íconos, esta función es el ÚNICO archivo a tocar.
 *
 *   BD (Lucide)          Material Icons (Android)
 *   ─────────────────    ─────────────────────────────
 *   stethoscope     →    Icons.Filled.LocalHospital
 *   heart-pulse     →    Icons.Filled.HealthAndSafety
 *   football        →    Icons.Filled.SportsSoccer
 *   ...
 *   (lo que no sepamos)→ Icons.Filled.Place  (pin de mapa)
 *
 * @return SIEMPRE un ImageVector: nunca null, nunca un emoji.
 */
fun iconForCategory(lucideIcon: String?): ImageVector = when (lucideIcon) {
    "stethoscope" -> Icons.Filled.LocalHospital
    "heart-pulse" -> Icons.Filled.HealthAndSafety
    "football" -> Icons.Filled.SportsSoccer
    "graduation-cap" -> Icons.Filled.School
    "school" -> Icons.Filled.AccountBalance
    "dumbbell" -> Icons.Filled.FitnessCenter
    "hotel" -> Icons.Filled.Hotel
    "utensils" -> Icons.Filled.Restaurant
    "scissors" -> Icons.Filled.ContentCut
    "tools" -> Icons.Filled.Handyman
    "wrench" -> Icons.Filled.Build
    "briefcase" -> Icons.Filled.Work
    "laptop" -> Icons.Filled.Laptop
    "store" -> Icons.Filled.Storefront
    "car" -> Icons.Filled.DirectionsCar
    "shopping-cart" -> Icons.Filled.ShoppingCart
    "ellipsis" -> Icons.Filled.MoreHoriz
    else -> Icons.Filled.Place
}
