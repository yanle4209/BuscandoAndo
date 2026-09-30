package com.herling.buscandoando.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

/**
 * Tema de BuscandoAndo.
 *
 * Es SIEMPRE oscuro (igual que la web) y NO usa "dynamic color"
 * porque eso dejaría que Android eligiera los colores y rompería
 * la identidad de marca.
 */

private val BuscandoAndoColors = darkColorScheme(
    // ----- Acentos -----
    primary = CanaryYellow,                // botones, links, íconos activos
    onPrimary = TextOnYellow,              // texto encima del amarillo
    primaryContainer = CanaryYellowDark,
    onPrimaryContainer = TextPrimary,

    secondary = GreyOlive,                 // elementos secundarios
    onSecondary = TextPrimary,

    tertiary = ChocolatePlum,              // acento cálido
    onTertiary = TextPrimary,

    // ----- Superficies -----
    background = DarkBackground,           // fondo general
    onBackground = TextPrimary,

    surface = DarkSurface,                 // tarjetas elevadas
    onSurface = TextPrimary,

    surfaceVariant = DarkCard,             // campos de texto, chips
    onSurfaceVariant = TextSecondary,

    surfaceContainer = DarkCard,
    surfaceContainerHigh = DarkCard,

    // ----- Bordes -----
    outline = DividerDark,
    outlineVariant = DividerDark,

    // ----- Errores -----
    error = StatusClosed,
    onError = TextPrimary,
)

@Composable
fun BuscandoAndoTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = BuscandoAndoColors,
        typography = BuscandoAndoTypography,
        content = content
    )
}
