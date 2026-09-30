# Diseño — Búsqueda por ubicación (R1–R4)

> Estado: **18 decisiones cerradas**, 3 pendientes.
> Este documento junta las decisiones y comprueba que no se chocan entre sí.
> Previa a cualquier código. Fuentes: `VISION.md` (visión del backend).

---

## 1. Los estados

Con 2 estados, R3.1 y R3.2 se contradicen:

- **R3.1** — al llegar: *"vuelve a GPS solo"*.
- **R3.2** — al salir de >5 km tras haber entrado: *"borra todo"*, pero también:
  *"en GPS normal, alejarse solo refresca, nunca resetea"*.

Una vez que llegaste **ya estás en GPS**. Sin memoria de que llegaste por el
destino, la segunda regla gana y **nunca se borra nada**.

Se necesitan **3 estados + 1 flag**:

| Estado | Punto activo |
|---|---|
| **S0 · ESPERA** | ninguno |
| **S1 · GPS** | posición real |
| **S2 · DESTINO** | cabecera municipal elegida |

**Flag `llegó`** — se pone en `true` al llegar (S2 → S1); se borra al resetear.

### Transiciones

| De | A | Disparo | Efecto |
|---|---|---|---|
| S0 | S1 | GPS disponible al abrir (R3.6) | — |
| S0 | S2 | sin GPS → elige municipio (R1.1) | busca contra cabecera |
| S1 | S2 | elige municipio **distinto** al suyo | — |
| S1 | S1 | elige **su propio** municipio (R3.3) | *no-op*: sigue en GPS, no resetea |
| S2 | S1 | **entra a 5 km** del destino (R3.1) | conserva texto/categoría · pág 1 · `llegó = true` |
| S1 | S0 | sale de >5 km **y `llegó`** (R3.2) | borra TODO · `llegó = false` |
| S1 | S1 | disparo C (R1.a) | conserva filtros · pág 1 · mapa recentra |

**Precedencia:** si coinciden *"cambió de municipio"* y *"salió de >5 km con `llegó`"*
→ **gana el reset**.

---

## 2. Disparos de refresco (R1.a)

Se refresca cuando **alguna** de estas cosas pasa:

1. Entra a **5 km** de una cabecera municipal.
2. Cambia de municipio.
3. Se aleja **≥ 500 m** del último punto consultado.

**Throttle:** mínimo **30 s** entre peticiones automáticas.

> **Alcance del throttle (choque 1):** solo limita refrescos automáticos **por
> movimiento**. Los cambios explícitos de punto — llegada, municipio manual,
> primera búsqueda — **no se limitan**. Si no, el refresco de llegada se
> descarta y te quedas viendo resultados de destino con el GPS ya dentro del círculo.

---

## 3. El punto activo

- **GPS** si está disponible (**R3.6**: al abrir, el GPS manda).
- Si no hay GPS → **elegir municipio es obligatorio** (**R1.1**): nunca se navega
  sin punto activo.
- El punto de un municipio es su **cabecera municipal** — edificio de
  ayuntamiento o, si no existe, edificio gubernamental (**R3**). No el centroide
  estadístico.
- La ciudad elegida se **recuerda entre sesiones** (`localStorage`, **R3.4**) —
  pero solo como base para cuando no hay GPS. **El destino no se reanuda.**
- Elige **su propio** municipio → **R3.3**: se valida y se asume; sigue en GPS.

> **Consecuencia:** hay que **eliminar el fallback `DR_CENTER`** (`Home.jsx`).
> "5 km desde un punto inventado" no significa nada. Al quitarlo, quien niegue
> el GPS verá el overlay — **elegir municipio tiene que ser de un toque**.

---

## 4. Contrato de consulta al API

Siempre lo mismo, en ambas plataformas:

```
lat + lng + radius=5     ← nunca city (R3.5)
text / category          ← se conservan en refresco (R2)
page                     ← se resetea a 1 en cada refresco (R2)
```

| Qué | Endpoint | ¿Ya sirve? |
|---|---|---|
| Resultados | `/businesses/?lat&lng&radius` | ✅ sí |
| Destacados de portada (R4.1) | `/businesses/?featured=true&lat&lng&radius` | ✅ sí |
| Destacados del buscador (R1.2) | `/featured-by-search/` | ❌ **falta lat/lng/radius** |

> **Choque 2:** `featured-by-search` solo entiende `text`, `category` y `city`.
> R1.2 da por hecho que filtra por distancia. **Hay que añadirle el mismo
> filtro haversine que ya usa `/businesses/`** — trabajo de backend no contado.

> **Choque 4 — "ciudad" cambia de significado:**
> hoy `city=Santiago` = *todo* el municipio (`icontains`); con R3.5 = círculo de
> **5 km desde la cabecera**. Se ven menos negocios por búsqueda de ciudad. Es
> lo decidido (R1), pero cambia lo que el usuario ve.

> **Choque 5 — el radio por defecto es 10, no 5:** `radius` default `10` en el
> backend y `radius: 10` en `Home.jsx`. Hoy **se busca a 10 km**.

---

## 5. Presentación de resultados

Principio rector: **si hay resultados disponibles, se enseñan — nunca tapados.**

- **a1** — fila de destacados solo si **hay destacados que coinciden con la
  búsqueda dentro de 5 km**; si no, no se dibuja.
- **m2** — mapa siempre junto a la lista en escritorio; en móvil **solo cuando
  no hay resultados**.
- **0 destacadas + 0 normales** → **overlay** sustituyendo a
  *"No se encontraron negocios"*.
- **R4.1** — la web conserva destacados en portada (a 5 km) · su fallback de
  recientes **también a 5 km** · **sin punto activo → solo overlay**.
- **Android** — solo overlay hasta la primera búsqueda.

### Asimetría web / Android (R4.1 × R4)

| | Primera consulta | Refrescos siguientes |
|---|---|---|
| **Web** | automática al abrir | automáticos (R2) |
| **Android** | **explícita** del usuario | automáticos (R2) |

---

## 6. Trabajo que se desprende

| # | Trabajo | Dónde |
|---|---|---|
| 1 | `featured-by-search` acepta `lat`/`lng`/`radius` | backend |
| 2 | Acotar `radius` a 5 (hoy default 10) | backend |
| 3 | `radius: 10` → `5` | `Home.jsx` |
| 4 | Quitar slider de radio | `SearchBar.jsx` |
| 5 | Filtro Ciudad → selector que fija el punto activo | `SearchBar.jsx` |
| 6 | Eliminar fallback `DR_CENTER` | `Home.jsx` |
| 7 | Guardar "último punto consultado" + timestamp (throttle 30 s) | ambas |
| 8 | Persistir municipio base en `localStorage` | web |
| 9 | Quitar chip de 2 km | Android |
| 10 | **Lista de cabeceras municipales** | *dato* |
| 11 | **Destacados** (4 hoy, niveles 2–4, ninguno nivel 1) | *dato* |

---

## 7. Pendientes

| # | Qué | Nota |
|---|---|---|
| 1 | **Fuente de cabeceras municipales** | Plan: listado por provincia → OSM → fallback. *Previa a todo.* |
| 2 | **Cobertura de datos por municipio** | Pospuesta al final. *Puede invalidar lo decidido.* |
| 3 | **Destacados** | Atada al 2: marcar más no sirve fuera de donde hay datos. |
| 4 | Confirmación: destino elegido + reabrir **con GPS** → ¿se reanuda? | R3.6 literal → **no, vuelve a tu GPS**. |

---

## 8. Las 18 decisiones

### R1 — Búsqueda exclusiva a 5 km
- **R1** — las búsquedas son única y exclusivamente a 5 km del punto del usuario.
- **R1.a** — disparo C: refrescar al ∨ entrar a 5 km de una cabecera ∨ cambiar de
  municipio ∨ alejarse ≥500 m. Mínimo 30 s entre peticiones.
- **R1.1** — sin GPS → elegir municipio obligatorio. Nunca navegar sin punto activo.
- **R1.2** — los destacados del buscador **sí** entran en el filtro de 5 km.
- **R1.3** — alcance a ambas plataformas: Android pierde el chip de 2 km; el
  selector de radio pasa a fijo 5 km.

### R2 — Refresco automático
- **R2** — al refrescar se conservan texto/categoría y se resetea a página 1.
- **R2.1** — el mapa se recentra solo en cada refresco (atado al disparo, no a un
  temporizador → no salta si el usuario está quieto).

### R3 — Punto activo y modo destino
- **R3** — el punto se define por **cabecera municipal**, no centroide. La lista
  de cabeceras sirve además para el selector manual: un solo dato, dos usos.
- **R3.1** — al llegar (entrar a 5 km del destino) → vuelve a GPS solo, sin botón.
- **R3.2** — salir de >5 km tras haber entrado → vuelta a espera + borra todo.
  Si nunca entra, se queda en modo destino, **sin caducidad**. El reinicio es
  exclusivo de modo destino.
- **R3.3** — si elige su propio municipio → lo valida, lo asume → automático directo.
- **R3.4** — la ciudad elegida se recuerda entre sesiones.
- **R3.5** — `city` deja de ser filtro por nombre y pasa a coordenadas + 5 km.
  Ningún cliente mandará `city` al API.
- **R3.6** — al abrir, el GPS manda si está disponible; lo recordado solo cuando
  no hay GPS.

### R4 — Presentación
- **R4** — en Android no debe aparecer nada (solo el overlay) hasta la primera búsqueda.
- **R4.1** — opción A: la web **conserva los destacados en portada**; Android queda
  solo con overlay. Asimetría intencional. Condiciones: (1) destacados de portada
  a 5 km del punto activo; (2) su fallback también a 5 km; (3) sin punto activo →
  solo overlay.
- **a1** — fila de destacados solo si hay destacados en 5 km.
- **m2** — mapa siempre junto a la lista en escritorio; en móvil solo sin resultados.
