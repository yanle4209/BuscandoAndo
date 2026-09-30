package com.herling.buscandoando.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.BottomSheetDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.herling.buscandoando.R
import com.herling.buscandoando.core.data.dto.BusinessDetail
import com.herling.buscandoando.core.data.dto.HourDto
import com.herling.buscandoando.ui.iconForCategory
import com.herling.buscandoando.ui.theme.CanaryYellow
import com.herling.buscandoando.ui.theme.DarkCard
import com.herling.buscandoando.ui.theme.DarkSurface
import com.herling.buscandoando.ui.theme.DividerDark
import com.herling.buscandoando.ui.theme.StatusClosed
import com.herling.buscandoando.ui.theme.TextMuted
import com.herling.buscandoando.ui.theme.TextPrimary
import com.herling.buscandoando.ui.theme.TextSecondary
import com.herling.buscandoando.ui.theme.WhiteSmoke
import kotlinx.coroutines.launch

/**
 * FASE 4 — Hoja modal con el detalle de un negocio.
 *
 * Equivalente en la web: tu <Modal> de React.
 *
 *  React                          Compose
 *  ─────────────────────────      ──────────────────────────────
 *  {slug && <Modal/>}             if (state.detailSlug != null) { ... }
 *  <Modal onClose={...}/>         ModalBottomSheet(onDismissRequest = ...)
 *  useEffect(() => fetch(slug))   loadDetail() en el ViewModel
 *
 * REGLA: esta composable NO hace fetch. Solo recibe `state` y
 * avisa de dos cosas: "lo cerraron" y "quieren reintentar".
 *
 * `@OptIn(ExperimentalMaterial3Api::class)` = firma explícita de que
 * aceptamos una API de Material 3 que todavía puede cambiar.
 * Es la forma correcta de usarlo; sin esto ni compila.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BusinessDetailSheet(
    state: HomeUiState,
    onDismiss: () -> Unit,
    onRetry: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()

    // Cierra ANIMANDO la hoja hacia abajo y recién al terminar
    // limpia el estado (evita que se corte la animación).
    val hideThenDismiss: () -> Unit = {
        scope.launch { sheetState.hide() }.invokeOnCompletion { onDismiss() }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,   // tap en el fondo o botón Atrás
        sheetState = sheetState,
        containerColor = DarkCard,
        dragHandle = { BottomSheetDefaults.DragHandle(color = DividerDark) },
    ) {
        val detail = state.detail
        val error = state.detailError

        when {
            detail != null -> DetailBody(detail = detail, onClose = hideThenDismiss)
            error != null -> SheetError(message = error, onRetry = onRetry)
            else -> SheetLoading()   // detailSlug != null y aún no llegó nada
        }
    }
}

// ═══════════════════ CONTENIDO DEL DETALLE ═══════════════════

@Composable
private fun DetailBody(detail: BusinessDetail, onClose: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())   // todo el sheet se desliza
            .padding(bottom = 24.dp),
    ) {
        // ── Cabecera: foto grande, con el ícono detrás como fallback ──
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(170.dp)
                .background(DarkSurface),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = iconForCategory(detail.category_icon),
                contentDescription = null,
                tint = TextSecondary,
                modifier = Modifier.size(64.dp),
            )

            val photo = detail.images.firstOrNull()?.image_url
            if (!photo.isNullOrBlank()) {
                AsyncImage(
                    model = photo,
                    contentDescription = detail.name,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }

        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp)) {
            Spacer(Modifier.height(14.dp))

            // ── Nombre + botón cerrar ──
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = detail.name,
                    color = WhiteSmoke,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Black,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                IconButton(onClick = onClose) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = stringResource(R.string.detail_close),
                        tint = TextSecondary,
                    )
                }
            }

            // ── Categoría + estado operativo ──
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = detail.category_name ?: stringResource(R.string.home_no_category),
                    color = TextMuted,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.width(12.dp))
                Box(
                    modifier = Modifier
                        .size(9.dp)
                        .clip(CircleShape)
                        .background(statusColorOf(detail.effective_status)),
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = detail.effective_status_name ?: "",
                    color = statusColorOf(detail.effective_status),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                )
            }

            // ── Descripción ──
            val description = detail.description?.takeIf { it.isNotBlank() }
                ?: detail.short_description?.takeIf { it.isNotBlank() }
            if (!description.isNullOrBlank()) {
                Spacer(Modifier.height(14.dp))
                Text(
                    text = description,
                    color = TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            // ── Secciones: ubicación / contacto / horario ──
            LocationSection(detail)
            ContactSection(detail)
            ScheduleSection(detail)
        }
    }
}

// ─────────────────── UBICACIÓN ───────────────────

/**
 * Trocea una dirección por comas y descarta las piezas vacías.
 *
 * El backend arma `full_address` concatenando campos aunque estén en
 * `""`, de modo que a veces nos llega `", Moca, Espaillat"` o
 * `"Calle 1, , Moca"`. Este filtro deja solo lo que aporta.
 */
private fun String.addressParts(): List<String> =
    split(",").map { it.trim() }.filter { it.isNotEmpty() }

@Composable
private fun LocationSection(detail: BusinessDetail) {
    val loc = detail.location

    // El servidor ya nos trae la dirección ARMADA en full_address.
    // Si un día no viene, la montamos nosotros con las piezas.
    val raw = loc?.full_address?.takeIf { it.isNotBlank() }
        ?: listOfNotNull(loc?.street, loc?.sector, loc?.municipality, loc?.province)
            .joinToString(", ")

    // ⚠️ El backend concatena campos aunque vengan en "", así que a
    // veces llega ", Moca, Espaillat" (coma suelta al principio) o
    // termina en ",". Troceamos y descartamos lo vacío.
    val address = raw.addressParts().joinToString(", ").takeIf { it.isNotBlank() }

    // País solo si la dirección todavía no lo trae.
    // (Sin esto repetíamos "República Dominicana" y, si postal_code
    //  venía en "" , aparecía una coma suelta al principio.)
    val country = loc?.country
        ?.takeIf { it.isNotBlank() && address?.contains(it, true) != true }

    val lines = listOfNotNull(address, country)

    SectionShell(title = stringResource(R.string.detail_location), icon = Icons.Default.Place) {
        if (lines.isEmpty()) {
            NoInfo()
        } else {
            lines.forEach { InfoLine(icon = Icons.Default.Place, text = it) }
        }
    }
}

// ─────────────────── CONTACTO ───────────────────

@Composable
private fun ContactSection(detail: BusinessDetail) {
    val c = detail.contact
    val lines = listOfNotNull(
        c?.phone?.takeIf { it.isNotBlank() }?.let { Icons.Default.Phone to it },
        c?.whatsapp?.takeIf { it.isNotBlank() }?.let { Icons.AutoMirrored.Filled.Chat to it },
        c?.email?.takeIf { it.isNotBlank() }?.let { Icons.Default.Email to it },
        c?.website?.takeIf { it.isNotBlank() }?.let { Icons.Default.Language to it },
        c?.contact_person?.takeIf { it.isNotBlank() }?.let { Icons.Default.Person to it },
    )

    SectionShell(title = stringResource(R.string.detail_contact), icon = Icons.Default.Phone) {
        if (lines.isEmpty()) {
            NoInfo()
        } else {
            lines.forEach { (icon, text) -> InfoLine(icon = icon, text = text) }
        }
    }
}

// ─────────────────── HORARIO ───────────────────

@Composable
private fun ScheduleSection(detail: BusinessDetail) {
    SectionShell(title = stringResource(R.string.detail_schedule), icon = Icons.Default.AccessTime) {
        if (detail.hours.isEmpty()) {
            NoInfo()
        } else {
            detail.hours.forEach { HourRow(hour = it) }
        }
    }
}

/**
 * "08:00:00" -> "08:00"
 * Corta los segundos: `substringBeforeLast(":")` se queda con todo
 * lo anterior al ÚLTIMO dos puntos.
 */
private fun String.toHhMm(): String = substringBeforeLast(":")

@Composable
private fun HourRow(hour: HourDto) {
    // Cerrado si el servidor lo dice O si no mandó horas
    // (los domingos vienen con open_time: null).
    val closed = hour.is_closed || hour.open_time == null || hour.close_time == null

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = hour.day,
            color = TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
        if (hour.is_holiday) {
            Text(
                text = "· feriado  ",
                color = TextMuted,
                style = MaterialTheme.typography.labelSmall,
            )
        }
        Text(
            text = if (closed) {
                stringResource(R.string.detail_closed_day)
            } else {
                "${hour.open_time!!.toHhMm()} – ${hour.close_time!!.toHhMm()}"
            },
            color = if (closed) StatusClosed else CanaryYellow,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Bold,
        )
    }
}

// ═══════════════════ PIEZAS REUTILIZABLES ═══════════════════

/** Encabezado amarillo + línea divisoria. Igual que en la web. */
@Composable
private fun SectionShell(
    title: String,
    icon: ImageVector,
    content: @Composable () -> Unit,
) {
    Spacer(Modifier.height(20.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = CanaryYellow,
            modifier = Modifier.size(17.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = title,
            color = CanaryYellow,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
    }
    HorizontalDivider(color = DividerDark, thickness = 1.dp, modifier = Modifier.padding(top = 8.dp))
    Spacer(Modifier.height(4.dp))
    content()
}

/** Una línea: ícono gris + texto. */
@Composable
private fun InfoLine(icon: ImageVector, text: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = TextMuted,
            modifier = Modifier.size(17.dp),
        )
        Spacer(Modifier.width(10.dp))
        Text(
            text = text,
            color = TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun NoInfo() {
    Text(
        text = stringResource(R.string.detail_no_info),
        color = TextMuted,
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier.padding(vertical = 6.dp),
    )
}

// ═══════════════════ CARGANDO / ERROR ═══════════════════

@Composable
private fun SheetLoading() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator(color = CanaryYellow, strokeWidth = 3.dp)
        Spacer(Modifier.height(14.dp))
        Text(
            text = stringResource(R.string.detail_loading),
            color = TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun SheetError(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 32.dp, vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = Icons.Default.Warning,
            contentDescription = null,
            tint = StatusClosed,
            modifier = Modifier.size(40.dp),
        )
        Spacer(Modifier.height(12.dp))
        Text(
            text = stringResource(R.string.detail_error),
            color = TextPrimary,
            style = MaterialTheme.typography.titleMedium,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            text = message,
            color = TextMuted,
            style = MaterialTheme.typography.bodySmall,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(18.dp))
        OutlinedButton(
            onClick = onRetry,
            border = BorderStroke(1.dp, CanaryYellow),
        ) {
            Icon(
                imageVector = Icons.Default.Refresh,
                contentDescription = null,
                tint = CanaryYellow,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(text = stringResource(R.string.home_error_retry), color = CanaryYellow)
        }
    }
}
