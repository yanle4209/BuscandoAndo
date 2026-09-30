package com.herling.buscandoando

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.herling.buscandoando.ui.home.HomeScreen
import com.herling.buscandoando.ui.home.HomeViewModel
import com.herling.buscandoando.ui.map.MapScreen
import com.herling.buscandoando.ui.theme.BuscandoAndoTheme
import com.herling.buscandoando.ui.theme.CanaryYellow
import com.herling.buscandoando.ui.theme.CanaryYellowDark
import com.herling.buscandoando.ui.theme.CanaryYellowLight
import com.herling.buscandoando.ui.theme.ChocolatePlum
import com.herling.buscandoando.ui.theme.DarkBackground
import com.herling.buscandoando.ui.theme.DarkCard
import com.herling.buscandoando.ui.theme.DarkSurface
import com.herling.buscandoando.ui.theme.DividerDark
import com.herling.buscandoando.ui.theme.GreyOlive
import com.herling.buscandoando.ui.theme.Level1Gold
import com.herling.buscandoando.ui.theme.Level2Silver
import com.herling.buscandoando.ui.theme.Level3Bronze
import com.herling.buscandoando.ui.theme.Level4Brown
import com.herling.buscandoando.ui.theme.StatusBySchedule
import com.herling.buscandoando.ui.theme.StatusClosed
import com.herling.buscandoando.ui.theme.StatusOpen
import com.herling.buscandoando.ui.theme.TextBrown
import com.herling.buscandoando.ui.theme.TextMuted
import com.herling.buscandoando.ui.theme.TextOnYellow
import com.herling.buscandoando.ui.theme.TextPrimary
import com.herling.buscandoando.ui.theme.TextSecondary
import com.herling.buscandoando.ui.theme.WhiteSmoke
import com.herling.buscandoando.ui.theme.BrandBlack

/** Un color de la paleta: nombre visible + valor hex (para la guía). */
data class Swatch(
    val label: String,
    val hex: String,
    val color: Color,
    /** Color del texto que va encima, para que siempre contraste. */
    val onColor: Color = TextPrimary,
)

/** Agrupa colores bajo un título. */
data class SwatchGroup(val title: String, val items: List<Swatch>)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            BuscandoAndoTheme {
                // Fase 5: raíz con navegación Home <-> Mapa.
                // La guía de estilos sigue disponible en
                // StyleGuideScreen() si necesitas revisarla.
                AppRoot()
            }
        }
    }
}

/**
 * Navegación de la app SIN librería externa.
 *
 * En React sería:
 *
 *   const [screen, setScreen] = useState("home");
 *   screen === "map" ? <MapScreen/> : <HomeScreen/>;
 *
 * `rememberSaveable` = el `useState` que SOBREVIVE a que Android mate
 * la app por falta de memoria: el valor se guarda en el Bundle y se
 * restaura solo.
 *
 * ⚠️ DETALLE CLAVE: el `HomeViewModel` se crea AQUÍ y se le pasa a
 * las dos pantallas. Así el mapa y el listado comparten los mismos
 * datos, el mismo filtro y la misma hoja de detalle abierta. Si se
 * creara dentro de cada pantalla, cada cambio de pantalla re-descargará
 * todo otra vez.
 */
@Composable
private fun AppRoot(viewModel: HomeViewModel = viewModel()) {
    var screen by rememberSaveable { mutableStateOf("home") }

    when (screen) {
        "map" -> MapScreen(
            viewModel = viewModel,
            onBack = { screen = "home" },
        )

        else -> HomeScreen(
            viewModel = viewModel,
            onOpenMap = { screen = "map" },
        )
    }
}

@Composable
fun StyleGuideScreen() {
    val groups = paletteGroups()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        modifier = Modifier.fillMaxSize()
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            item {
                Column {
                    Text(
                        text = stringResource(R.string.styleguide_title),
                        style = MaterialTheme.typography.headlineLarge,
                        color = CanaryYellow
                    )
                    Text(
                        text = stringResource(R.string.styleguide_subtitle),
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary
                    )
                }
            }

            items(groups) { group ->
                SwatchGroupCard(group)
            }

            item { Spacer(Modifier.height(8.dp)) }
        }
    }
}

@Composable
private fun SwatchGroupCard(group: SwatchGroup) {
    Column {
        Text(
            text = group.title,
            style = MaterialTheme.typography.titleMedium,
            color = TextPrimary,
            modifier = Modifier.padding(bottom = 10.dp)
        )

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(DarkCard)
                .padding(vertical = 6.dp)
        ) {
            group.items.forEach { swatch ->
                SwatchRow(swatch)
            }
        }
    }
}

@Composable
private fun SwatchRow(swatch: Swatch) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(38.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(swatch.color)
                .border(
                    width = 1.dp,
                    color = DividerDark,
                    shape = RoundedCornerShape(8.dp)
                )
        )

        Spacer(Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = swatch.label,
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                text = swatch.hex,
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted
            )
        }

        // Chip que muestra cómo se ve el color usado como fondo
        Box(
            modifier = Modifier
                .background(swatch.color, RoundedCornerShape(6.dp))
                .padding(horizontal = 10.dp, vertical = 5.dp)
        ) {
            Text(
                text = "Aa",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = swatch.onColor
            )
        }
    }
}

private fun paletteGroups(): List<SwatchGroup> = listOf(
    SwatchGroup(
        title = "Colores de marca",
        items = listOf(
            Swatch("Amarillo canario", "#B3B334", CanaryYellow, TextOnYellow),
            Swatch("Amarillo claro", "#D6D65E", CanaryYellowLight, TextOnYellow),
            Swatch("Amarillo oscuro", "#8A8A22", CanaryYellowDark, TextOnYellow),
            Swatch("Gris olivo", "#88898A", GreyOlive),
            Swatch("Chocolate plum", "#543335", ChocolatePlum),
            Swatch("Negro marca", "#000600", BrandBlack),
            Swatch("White smoke", "#F3F3F3", WhiteSmoke, TextOnYellow),
        )
    ),
    SwatchGroup(
        title = "Fondos y superficies",
        items = listOf(
            Swatch("Fondo general (--dark)", "#1A1A1A", DarkBackground),
            Swatch("Superficie elevada", "#212121", DarkSurface),
            Swatch("Contenedor tarjetas", "#252525", DarkCard),
            Swatch("Divisores / bordes", "#2A2A2A", DividerDark),
        )
    ),
    SwatchGroup(
        title = "Texto",
        items = listOf(
            Swatch("Texto principal", "#FFFFFF", TextPrimary),
            Swatch("Texto secundario", "#AAAAAA", TextSecondary),
            Swatch("Texto apagado", "#666666", TextMuted),
            Swatch("Texto marrón (tarjetas)", "#543335", TextBrown),
            Swatch("Sobre amarillo", "#1A1A1A", TextOnYellow),
        )
    ),
    SwatchGroup(
        title = "Estados operativos",
        items = listOf(
            Swatch("Abierto", "#4CAF50", StatusOpen, TextOnYellow),
            Swatch("Cerrado", "#E53935", StatusClosed),
            Swatch("Por horario", "#FFA726", StatusBySchedule, TextOnYellow),
        )
    ),
    SwatchGroup(
        title = "Niveles de destacado",
        items = listOf(
            Swatch("Nivel 1 · oro", "#B3B334", Level1Gold, TextOnYellow),
            Swatch("Nivel 2 · plata", "#A0A0A0", Level2Silver, TextOnYellow),
            Swatch("Nivel 3 · bronce", "#CD7F32", Level3Bronze),
            Swatch("Nivel 4 · marrón", "#8B7355", Level4Brown),
        )
    ),
)

@Preview(showBackground = true, backgroundColor = 0xFF1A1A1A)
@Composable
private fun StyleGuidePreview() {
    BuscandoAndoTheme {
        StyleGuideScreen()
    }
}
