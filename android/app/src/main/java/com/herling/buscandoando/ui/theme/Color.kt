package com.herling.buscandoando.ui.theme

import androidx.compose.ui.graphics.Color

/*
 * ============================================================
 *  PALETA OFICIAL BUSCANDOANDO
 *  Copiada de frontend/src/index.css: mismo lienzo blanco y
 *  mismos valores que la web (y el panel de administracion).
 *
 *  Regla de contraste: sobre blanco, el amarillo SOLO va en
 *  filetes y rellenos; para texto e iconos se usa el amarillo
 *  legible (GoldInk, 4,9:1) o el marron.
 * ============================================================
 */

// ----- Colores de marca -----
val CanaryYellow = Color(0xFFFBBF24)      // Amarillo BuscandoAndo (--yellow)
val CanaryYellowLight = Color(0xFFFCD34D) // Para pressed/hover (--yellow-light)
val CanaryYellowDark = Color(0xFFD99A0B)  // Para variantes (primaryContainer)
val BrandBrown = Color(0xFF513E0C)        // Marron (--brown): titulos de marca
val Gold = Color(0xFFA67E18)              // Dorado (--gold): nombre en la ficha
val GoldInk = Color(0xFF8F6C14)           // Amarillo legible (--yellow-ink)
val GreyOlive = Color(0xFF66615A)         // Gris olivo calido (--grey)
val ChocolatePlum = Color(0xFF513E0C)     // (heredado) marron de marca
val BrandBlack = Color(0xFF000600)        // Negro marca        (--black)

// ----- Lienzo y superficies (blanco literal, como la web) -----
// La web pinta de #ffffff las TRES zonas y separa las superficies con
// el filete, nunca con un gris de fondo (frontend/src/index.css).
val CanvasWhite = Color(0xFFFFFFFF)        // Fondo de pagina   (--bg)
val SurfaceWhite = Color(0xFFFFFFFF)       // Buscador, barra   (--surface)
val CardWhite = Color(0xFFFFFFFF)          // Tarjetas, ficha   (--surface-2)
val Hairline = Color(0xFFE2E1C9)           // Unico gris de borde (--border)
val HairlineStrong = Color(0xFFD4D3B6)     // Buscador y chips  (--border-strong)

// ----- Texto -----
val TextPrimary = Color(0xFF1F1A1A)        // Tinta             (--ink)
val TextSecondary = Color(0xFF5B564D)      // Texto suave       (--ink-soft)
val TextMuted = Color(0xFF66615A)          // Metadatos         (--grey)
val TextBrown = Color(0xFF8F6C14)          // Texto dorado      (--yellow-ink)
val TextOnYellow = Color(0xFF1F1A1A)       // Texto sobre amarillo

// ----- Estados operativos (effective_status) -----
// Mismos tonos que las etiquetas de estado de la web
// (BusinessCard.css: #15803d / #dc2626 / #c2410c), que ya son los que
// pasan 4,5:1 como texto sobre blanco.
val StatusOpen = Color(0xFF15803D)         // 'abierto'     -> Abierto
val StatusClosed = Color(0xFFDC2626)       // 'cerrado'     -> Cerrado
val StatusBySchedule = Color(0xFFC2410C)   // 'por-horario' -> Por Horario

// ----- Fila de datos de la tarjeta (BusinessCard.css) -----
// El gris de las filas (dirección, teléfono…) es el mismo --grey que
// ya está arriba (#66615a = TextMuted); estos dos son los únicos
// valores de esa hoja que faltaban en la paleta.
val CardRowInk = Color(0xFF423E38)       // .biz-card__row (texto)
val WhatsAppGreen = Color(0xFF25D366)    // .biz-card__row--whatsapp (icono)

// ----- Niveles de destacado -----
// ELIMINADOS: ya no hay escalonado por nivel. Hay una sola pastilla
// "Destacado" (blanca, texto dorado) y el borde de la tarjeta.
// (Web: .biz-card__badge / .biz-card__badge)

// ----- Colores de categoria (para el icono) -----
val CategoryTint = Color(0xFFFBBF24)

// Borde de las tarjetas destacadas (amarillo al 55% sobre blanco)
val FeaturedBorder = Color(0x8CFBBF24)
