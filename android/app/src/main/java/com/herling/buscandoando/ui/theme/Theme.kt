package com.herling.buscandoando.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

/**
 * Tema de BuscandoAndo.
 *
 * Es SIEMPRE claro (igual que la web, que pinta de blanco literal
 * #ffffff sus tres zonas) y NO usa "dynamic color" porque eso
 * dejaría que Android eligiera los colores y rompería la identidad
 * de marca.
 */

private val BuscandoAndoColors = lightColorScheme(
    // ----- Acentos -----
    primary = CanaryYellow,                // filetes y rellenos
    onPrimary = TextOnYellow,              // texto encima del amarillo
    primaryContainer = CanaryYellowDark,
    onPrimaryContainer = TextOnYellow,

    secondary = GreyOlive,                 // elementos secundarios
    onSecondary = TextOnYellow,

    tertiary = BrandBrown,                 // acento calido
    onTertiary = TextOnYellow,

    // ----- Superficies (blanco literal) -----
    background = CanvasWhite,              // fondo general
    onBackground = TextPrimary,

    surface = SurfaceWhite,                // buscador, barra de mapa
    onSurface = TextPrimary,

    surfaceVariant = CardWhite,            // campos de texto, chips
    onSurfaceVariant = TextSecondary,

    surfaceContainer = CardWhite,
    surfaceContainerHigh = CardWhite,

    // ----- Bordes -----
    outline = Hairline,
    outlineVariant = Hairline,

    // ----- Errores -----
    error = StatusClosed,
    onError = TextOnYellow,
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
