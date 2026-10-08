package com.herling.buscandoando.ui.home

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.herling.buscandoando.ui.theme.BrandBrown
import com.herling.buscandoando.ui.theme.CanaryYellow
import kotlinx.coroutines.launch

/**
 * Dónde van los controles del carrusel.
 *
 * La web usa UN único carrusel (ImageCarousel.jsx) y cambia su pinta
 * con dos selectores distintos:
 *
 *   Portada  → dentro de .biz-card__cover: los puntos suben a
 *              `top: 5px` (blanco translúcido, activo amarillo) para
 *              no pisar el nombre, que va abajo sobre el velo.
 *   Ficha    → dentro de .modal-carousel: los puntos quedan DEBAJO de
 *              la foto (gris, activo marrón) y las flechas crecen a
 *              36px con fondo marrón semitransparente.
 */
enum class EstiloCarrusel { Portada, Ficha }

/**
 * Carrusel de fotos de ImageCarousel.jsx, en Compose.
 *
 * Deslizable (HorizontalPager) y con los mismos controles que la web:
 * puntos + flechas. Se comparte entre la tarjeta (HomeScreen) y la
 * ficha (BusinessDetailSheet), igual que la web comparte el mismo
 * componente en `.biz-card__cover` y en `.modal-carousel`.
 *
 * El contenido es una lista de URLs ya resueltas: a esta capa no le
 * interesa si vinieron de `image_url` o de `image`.
 */
@Composable
internal fun FotosCarrusel(
    imagenes: List<String>,
    modifier: Modifier = Modifier,
    estilo: EstiloCarrusel = EstiloCarrusel.Portada,
) {
    if (imagenes.isEmpty()) return

    val pagina = rememberPagerState { imagenes.size }
    val alcance = rememberCoroutineScope()

    // Flechas: 20dp sobre la foto de la tarjeta, 36dp sobre el fondo
    // blanco de la ficha (la web las agranda ahí).
    val altoFlecha: Dp = if (estilo == EstiloCarrusel.Portada) 20.dp else 36.dp
    val fondoFlecha = if (estilo == EstiloCarrusel.Portada) {
        Color.Black.copy(alpha = 0.6f)
    } else {
        Color(0xCC543135)   // rgba(84, 51, 53, 0.8), como .modal-carousel
    }

    /** Pinta los puntos: arriba (portada) o debajo (ficha). */
    @Composable
    fun Puntos(modifier: Modifier = Modifier) {
        val portada = estilo == EstiloCarrusel.Portada
        Row(modifier = modifier, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            imagenes.indices.forEach { i ->
                val activo = i == pagina.currentPage
                // Portada: 6dp gris/blanco, activo amarillo de 16dp.
                // Ficha:   8dp gris,     activo marrón de 20dp.
                val ancho by animateDpAsState(
                    targetValue = when {
                        portada && activo -> 16.dp
                        portada -> 6.dp
                        activo -> 20.dp
                        else -> 8.dp
                    },
                    label = "punto",
                )
                Box(
                    modifier = Modifier
                        .width(ancho)
                        .height(if (portada) 6.dp else 8.dp)
                        .clip(if (activo) RoundedCornerShape(3.dp) else CircleShape)
                        .background(
                            when {
                                portada && activo -> CanaryYellow
                                portada -> Color.White.copy(alpha = 0.65f)
                                activo -> BrandBrown
                                else -> Color(0xFF7D7768)
                            },
                        )
                        // El punto activo no hace nada: ya estás ahí.
                        .clickable(enabled = !activo) {
                            alcance.launch { pagina.animateScrollToPage(i) }
                        },
                )
            }
        }
    }

    /** Flechas ‹ › a media altura, a los dos lados. */
    @Composable
    fun Flechas(modifier: Modifier = Modifier) {
        Row(
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = if (estilo == EstiloCarrusel.Portada) 5.dp else 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            FlechaCarrusel(Icons.AutoMirrored.Filled.KeyboardArrowLeft, altoFlecha, fondoFlecha) {
                val anterior =
                    if (pagina.currentPage == 0) imagenes.lastIndex else pagina.currentPage - 1
                alcance.launch { pagina.animateScrollToPage(anterior) }
            }
            FlechaCarrusel(Icons.AutoMirrored.Filled.KeyboardArrowRight, altoFlecha, fondoFlecha) {
                val siguiente =
                    if (pagina.currentPage == imagenes.lastIndex) 0 else pagina.currentPage + 1
                alcance.launch { pagina.animateScrollToPage(siguiente) }
            }
        }
    }

    when (estilo) {
        EstiloCarrusel.Portada -> Box(modifier = modifier) {
            HorizontalPager(
                state = pagina,
                modifier = Modifier.fillMaxSize(),
            ) { indice ->
                PaginaFoto(imagenes[indice])
            }

            Puntos(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 5.dp),
            )
            Flechas(modifier = Modifier.align(Alignment.Center))
        }

        // La fila de puntos va DEBAJO de la foto: por eso la raíz es
        // una Column y la foto ocupa el resto con weight(1f).
        EstiloCarrusel.Ficha -> Column(modifier = modifier) {
            Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
                HorizontalPager(
                    state = pagina,
                    modifier = Modifier.fillMaxSize(),
                ) { indice ->
                    PaginaFoto(imagenes[indice])
                }
                Flechas(modifier = Modifier.align(Alignment.Center))
            }

            Puntos(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            )
        }
    }
}

/** Una foto del carrusel, recortada a rellenar (object-fit: cover). */
@Composable
private fun PaginaFoto(url: String) {
    AsyncImage(
        model = url,
        // null a propósito: el nombre del negocio ya lo expone el
        // texto de la ficha/tarjeta, y TalkBack no debe repetirlo.
        contentDescription = null,
        contentScale = ContentScale.Crop,
        modifier = Modifier.fillMaxSize(),
    )
}

/** Flecha del carrusel: círculo semitransparente con chevron blanco. */
@Composable
private fun FlechaCarrusel(icon: ImageVector, alto: Dp, fondo: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(alto)
            .clip(CircleShape)
            .background(fondo)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White,
            modifier = Modifier.size(if (alto > 24.dp) 22.dp else 14.dp),
        )
    }
}
