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
import androidx.core.view.WindowCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.herling.buscandoando.core.data.MunicipioStore
import com.herling.buscandoando.ui.home.HomeScreen
import com.herling.buscandoando.ui.home.HomeViewModel
import com.herling.buscandoando.ui.map.MapScreen
import com.herling.buscandoando.ui.theme.BuscandoAndoTheme
import com.herling.buscandoando.ui.theme.CanaryYellow
import com.herling.buscandoando.ui.theme.CanaryYellowDark
import com.herling.buscandoando.ui.theme.CanaryYellowLight
import com.herling.buscandoando.ui.theme.ChocolatePlum
import com.herling.buscandoando.ui.theme.Gold
import com.herling.buscandoando.ui.theme.GoldInk
import com.herling.buscandoando.ui.theme.BrandBrown
import com.herling.buscandoando.ui.theme.CanvasWhite
import com.herling.buscandoando.ui.theme.CardWhite
import com.herling.buscandoando.ui.theme.GreyOlive
import com.herling.buscandoando.ui.theme.Hairline
import com.herling.buscandoando.ui.theme.StatusBySchedule
import com.herling.buscandoando.ui.theme.StatusClosed
import com.herling.buscandoando.ui.theme.StatusOpen
import com.herling.buscandoando.ui.theme.SurfaceWhite
import com.herling.buscandoando.ui.theme.TextBrown
import com.herling.buscandoando.ui.theme.TextMuted
import com.herling.buscandoando.ui.theme.TextOnYellow
import com.herling.buscandoando.ui.theme.TextPrimary
import com.herling.buscandoando.ui.theme.TextSecondary
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
        // La app es SIEMPRE clara: sin esto, con el móvil en modo
        // oscuro Android dejaría los iconos de barra en BLANCO y no se
        // verían sobre nuestro fondo blanco.
        enableEdgeToEdge()
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = true
            isAppearanceLightNavigationBars = true
        }
        // R3.4: el municipio elegido se recuerda entre sesiones. Se
        // inicializa ANTES de que exista el primer ViewModel, así que
        // nunca se lee un SharedPreferences vacío.
        MunicipioStore.init(this)
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
                        color = BrandBrown
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
                .clip(RoundedCornerShape(12.dp))
                .background(CardWhite)
                // Sobre lienzo blanco el grupo se separa con filete,
                // igual que las tarjetas de la web.
                .border(1.dp, Hairline, RoundedCornerShape(12.dp))
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
                    color = Hairline,
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
            Swatch("Amarillo BuscandoAndo", "#FBBF24", CanaryYellow, TextOnYellow),
            Swatch("Amarillo claro", "#FCD34D", CanaryYellowLight, TextOnYellow),
            Swatch("Amarillo oscuro", "#D99A0B", CanaryYellowDark, TextOnYellow),
            Swatch("Gris olivo (--grey)", "#66615A", GreyOlive, TextOnYellow),
            Swatch("Marrón (--brown)", "#513E0C", ChocolatePlum, TextOnYellow),
            Swatch("Negro marca", "#000600", BrandBlack, TextOnYellow),
        )
    ),
    SwatchGroup(
        title = "Lienzo y superficies (blanco literal)",
        items = listOf(
            Swatch("Fondo de página (--bg)", "#FFFFFF", CanvasWhite),
            Swatch("Buscador / barra (--surface)", "#FFFFFF", SurfaceWhite),
            Swatch("Tarjetas / ficha", "#FFFFFF", CardWhite),
            Swatch("Filete (--border)", "#E2E1C9", Hairline),
        )
    ),
    SwatchGroup(
        title = "Texto",
        items = listOf(
            Swatch("Tinta principal (--ink)", "#1F1A1A", TextPrimary, TextOnYellow),
            Swatch("Texto suave (--ink-soft)", "#5B564D", TextSecondary, TextOnYellow),
            Swatch("Metadatos (--grey)", "#66615A", TextMuted, TextOnYellow),
            Swatch("Texto dorado (tarjetas)", "#8F6C14", TextBrown, TextOnYellow),
            Swatch("Sobre amarillo", "#1F1A1A", TextOnYellow, CanaryYellow),
        )
    ),
    SwatchGroup(
        title = "Estados operativos",
        items = listOf(
            Swatch("Abierto", "#15803D", StatusOpen, TextOnYellow),
            Swatch("Cerrado", "#DC2626", StatusClosed, TextOnYellow),
            Swatch("Por horario", "#C2410C", StatusBySchedule, TextOnYellow),
        )
    ),
    SwatchGroup(
        title = "Dorado y marrón (paleta nueva)",
        items = listOf(
            Swatch("Dorado títulos (--gold)", "#A67E18", Gold, TextOnYellow),
            Swatch("Dorado texto (--yellow-ink)", "#8F6C14", GoldInk, TextOnYellow),
            Swatch("Marrón (--brown)", "#513E0C", BrandBrown, TextOnYellow),
        )
    ),
)

@Preview(showBackground = true, backgroundColor = 0xFFFFFFFF)
@Composable
private fun StyleGuidePreview() {
    BuscandoAndoTheme {
        StyleGuideScreen()
    }
}
