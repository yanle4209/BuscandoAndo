package com.herling.buscandoando.ui.theme

import androidx.compose.ui.graphics.Color

/*
 * ============================================================
 *  PALETA OFICIAL BUSCANDOANDO
 *  Misma que el sitio web (frontend/src/index.css)
 * ============================================================
 */

// ----- Colores de marca -----
val CanaryYellow = Color(0xFFFBBF24)      // Amarillo BuscandoAndo (--yellow)
val CanaryYellowLight = Color(0xFFFCD34D) // Para pressed/hover (--yellow-light)
val CanaryYellowDark = Color(0xFFD99A0B)  // Para variantes (primaryContainer)
val BrandBrown = Color(0xFF513E0C)        // Marron (--brown): superficies
val Gold = Color(0xFFA67E18)              // Dorado: titulos (--gold)
val GoldInk = Color(0xFF8F6C14)           // Dorado: texto (--yellow-ink)
val GreyOlive = Color(0xFF88898A)         // Gris olivo         (--grey)
val ChocolatePlum = Color(0xFF513E0C)     // (heredado) marron de marca
val BrandBlack = Color(0xFF000600)        // Negro marca        (--black)
val WhiteSmoke = Color(0xFFF3F3F3)        // White smoke        (--white)

// ----- Fondos oscuros (tema web) -----
val DarkBackground = Color(0xFF1A1A1A)    // var(--dark)
val DarkSurface = Color(0xFF212121)       // Elevación leve
val DarkCard = Color(0xFF252525)          // Contenedor de tarjetas
val DividerDark = Color(0xFF2A2A2A)       // Bordes/líneas

// ----- Texto -----
val TextPrimary = Color(0xFFFFFFFF)       // Texto principal
val TextSecondary = Color(0xFFAAAAAA)     // Texto secundario
val TextMuted = Color(0xFF666666)         // Texto apagado
val TextBrown = Color(0xFF8F6C14)         // Texto que era marron -> dorado
val TextOnYellow = Color(0xFF1A1A1A)      // Texto sobre amarillo

// ----- Estados operativos (effective_status) -----
val StatusOpen = Color(0xFF4CAF50)        // 'abierto'   -> Abierto
val StatusClosed = Color(0xFFE53935)      // 'cerrado'   -> Cerrado
val StatusBySchedule = Color(0xFFFFA726)  // 'por-horario' -> Por Horario

// ----- Niveles de destacado -----
// ELIMINADOS: ya no hay escalonado por nivel. Hay una sola pastilla
// "Destacado" (blanca, texto dorado) y el borde de la tarjeta.
// (Web: .biz-card__badge / .biz-card__badge)

// ----- Colores de categoría (para el ícono) -----
val CategoryTint = Color(0xFFFBBF24)

// Borde de las tarjetas destacadas (amarillo al 55% sobre blanco)
val FeaturedBorder = Color(0x8CFBBF24)
