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
| Destacados del buscador (R1.2) | `/featured-by-search/` | ✅ sí |

> **Choque 2 (resuelto):** `featured-by-search` solo entendía `text`,
> `category` y `city`. Ya recibe `lat`/`lng`/`radius` y aplica el mismo
> haversine que `/businesses/`, así que los destacados entran en el
> mismo círculo de 5 km (R1.2).

> **Choque 4 (resuelto) — "ciudad" cambia de significado:**
> antes `city=Santiago` = *todo* el municipio (`icontains`); ahora la
> ciudad es **5 km desde la cabecera**. El parámetro `city` se ha
> retirado del API (R3.5): mandarlo no recorta nada.

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

Cerrado en los tres commits del 30-09-2026 (`651e327` backend → `a80abb3`
web → `a9142b7` Android).

| # | Trabajo | Dónde | Estado |
|---|---|---|---|
| 1 | `featured-by-search` acepta `lat`/`lng`/`radius` | backend | ✅ también en web y Android (R1.2) |
| 2 | Acotar `radius` a 5 (antes default 10) | backend | ✅ `parse_radio`, tope 5 |
| 3 | `radius: 10` → `5` | `Home.jsx` | ✅ slider fuera, `RADIO_KM = 5` |
| 4 | Quitar slider de radio | `SearchBar.jsx` | ✅ |
| 5 | Filtro Ciudad → selector que fija el punto activo | `SearchBar.jsx` | ✅ fuera de "Filtros", un toque |
| 6 | Eliminar fallback `DR_CENTER` | `Home.jsx` | ✅ sin punto → solo overlay |
| 7 | Guardar "último punto consultado" + timestamp (throttle 30 s) | ambas | ✅ `useReducer` + throttle con *trailing* |
| 8 | Persistir municipio base en `localStorage` | web | ✅ `buscandoando.municipio`, solo si no hay GPS |
| 9 | Quitar chip de 2 km | Android | ✅ `HomeUiState.RADIO_KM = 5` |
| 10 | **Lista de cabeceras municipales** | *dato* | ✅ `backend/data/cabeceras_municipales.csv` + `GET /api/cabeceras/` |
| 11 | **Destacados** (4 hoy, niveles 2–4, ninguno nivel 1) | *dato* | ⏳ ver §7 |

### Añadido en el camino

| Trabajo | Dónde |
|---|---|
| El overlay sustituye a "No se encontraron negocios" y a la portada sin punto (a1/m2) | `Home.jsx` |
| Aviso "elige tu municipio o activa tu ubicación" cuando no hay punto (R1.1) | `MapOverlay.jsx` |
| Las frases del overlay dejan de nombrar Moca/Espaillat: se ven en los 158 | `MapOverlay.jsx` |
| Efecto de `center` después del de marcas, para que el mapa reciente solo (R2.1) | `MapView.jsx` |
| Guardia de secuencia para que una respuesta vieja no pise una nueva | `Home.jsx` |

---

## 7. Pendientes

| # | Qué | Nota |
|---|---|---|
| 1 | ~~Fuente de cabeceras municipales~~ | ✅ **Resuelta** → `backend/data/cabeceras_municipales.csv` (158 filas). Ver §9. |
| 2 | **Cobertura de datos por municipio** | **En curso** → R5 publica solo lo que cumple el trío **en todo el país**; lo que no cumple va al reporte por municipio. R6 queda como **canal de envío** (§11.5), con **correctores asignados: ninguno por ahora**. Ver §10–§11. |
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

---

## 9. Cabeceras municipales — fuente y método

**Archivo:** `backend/data/cabeceras_municipales.csv` — 158 filas, una por municipio.

### Fuentes

| Qué | De dónde |
|---|---|
| Lista de municipios **por provincia** | Wikipedia — *Municipios de la República Dominicana* (158 municipios, 32 provincias) |
| Edificio de **ayuntamiento** | OpenStreetMap — `amenity=townhall` (97 en RD) |
| Fallback: **edificio gubernamental** | OpenStreetMap — `office=government` (305 en RD) |
| Fallback: **punto en el pueblo** | OpenStreetMap — `place=city\|town\|municipality\|village` (794) |
| Último recurso | centroide del polígono municipal (OSM `admin_level=6`, 157) |

### Cadena de preferencia

1. `ayuntamiento` — edificio cuyo nombre contiene el municipio
2. `ayuntamiento` — edificio a <4 km de la relación municipal
3. `gubernamental` — ídem
4. `nodo_lugar` — nodo de asentamiento con el **mismo nombre exacto**
5. `centroide` — centroide del polígono

### Validación

Todo punto se contrasta contra el centroide de su polígono municipal.
**Se descarta si está a >30 km** — eso detecta los emparejamientos falsos por
colisión de nombre (*Cristóbal ↔ San Cristóbal* a 124 km, *Sabaneta* a 149 km,
*Guayabal* a 75 km, *Consuelo* a 68 km). El umbral es generoso a propósito:
*Pedernales* está a 26.8 km de su centroide y es correcto, porque el municipio es enorme.

### Cobertura

| Fuente | Municipios |
|---|---|
| `ayuntamiento` | **52** |
| `gubernamental` | **22** |
| `nodo_lugar` | **75** |
| `centroide` | **9** |
| sin nada | **0** |

**149 de 158 (94 %) tienen el punto en el pueblo.** Ninguno se queda sin punto.

### Filas a revisar manualmente

Las 9 que cayeron al `centroide` no tienen asentamiento con nombre coincidente:
*Barahona, Hostos, Mao, Monte Cristi, Sabana Yegua, Sabaneta, San Juan,
Santo Domingo Norte, Villa Bisonó (Navarrete)*.

**`dist_centroide_km`** es una pista, no un error: mide la distancia entre el
punto elegido y el centroide del polígono. Muestra la **forma** del municipio,
no la calidad del punto — *Baní* está a 11.2 km y su ayuntamiento es correcto.

### Nota sobre el recuento

Las cifras de municipios no coinciden entre fuentes: ONE 2021 dice **157**,
el portal del Estado dice **158**, Wikipedia (2024) **158**, OSM modela **157**.
Se usó Wikipedia (158) como canónica por venir con provincia ya asignada.
OJO: `municipality` ≠ `distrito municipal` (235) — los distritos municipales
**no** son cabeceras y no entran en este listado.

---

## 10. Publicación automática (R5)

> Nueva decisión, nacida de la conversación sobre cobertura.
> **Deja el flujo manual intacto y le añade una excepción marcada.**

### La regla

Un registro **importado** que cumpla el trío mínimo

```
nombre + teléfono + punto
```

→ **se publica solo**. El resto de campos (horario, WhatsApp, correo, estado,
categoría fina…) → se marcan **pendientes** → entran en la cola de corrección.

> **La dirección no se exige**: el punto geográfico la sustituye. En la RD la
> dirección formal casi no existe — la gente dice *"detrás del parque"*.

### Ámbito y umbrales (decidido)

- **Todo el país**, no solo donde hoy hay fichas: poblar la base con
  todos los negocios que encontremos **y que cumplan el trío**.
- **El teléfono es obligatorio** — no es un extra: es el segundo
  elemento del trío. Sin exigirlo entrarían candidatos a los que no se
  puede llamar.
- **Los que no cumplen no se descartan**: van al reporte de §11.1,
  agrupados **por municipio**, para ir editándolos y publicándolos a mano.

### Lo que NO cambia

- Creación manual → sigue `En Revisión` → **el admin publica** (`VISION.md` intacto).
- Nada se rellena por inventar: lo que falta **queda visible como pendiente**.

### Procedencia

| Marca | Quién llega así |
|---|---|
| `importado` | el automático — **visible, pero señalado** |
| `verificado` | pasó por revisión humana |

El usuario ve la calidad de la ficha sin que se pierda el control.

### Cómo se modela lo "pendiente"

**Calculado** — el campo está vacío → pendiente. **Cero estructura nueva.**

**+ `procedencia`** — lo que viene del servicio entra marcado.

Cubren los dos casos (*falta* y *entra sin verificar*) **sin campos nuevos**.

### Derivadas

- **La corrección deja de ser reactiva** (alguien ve un error) **y se vuelve
  proactiva**: el sistema sabe qué le falta y lo pide → **R6, §11**.
- **Dos canales**: el público **anónimo** corrige errores en fichas publicadas
  (endpoint ya anónimo, ya existe); los **correctores contratados** rellenan
  pendientes. → **§11.3**
- **Alimenta el 5 km**: solo importa dentro de las circunferencias de las
  cabeceras de §9 — importar lejos del centro no entra en ningún círculo.

### Medición — 5 km sobre la cabecera de Moca (`19.3964, -70.5274`)

**Fichas reales (producción — las 325)**

| Radio | Fichas | % |
|---|---|---|
| **5 km** — lo que fija R1 | **131** | 40 % |
| 10 km — default actual | 322 | 99 % |

**Candidatos de OSM dentro de ese mismo círculo**

| | |
|---|---|
| Candidatos | **101** (+5 sin nombre → descartados) |
| Con **teléfono** | **17** ← el cuello de botella |
| Con dirección formal (`addr:*`) | 50 |
| Con horario | 9 |
| Con web | 5 |
| **Cumplen el trío** | **17** |

**Lo que enseña**

1. **La dirección no era el cuello de botella**: con `addr:*` salen 16, sin
   exigirlo salen 17. **Manda el teléfono.**
2. **OSM cubre el 77 % de lo que hay** en el círculo — 101 de 131. (Antes
   parecía 31 % porque comparaba contra los 325 del municipio entero.)
3. **Pero solo 17 de esos 101 traen teléfono → 13 % del círculo.**
4. **En producción el teléfono es aún peor: 24 de 325 (7 %). WhatsApp: 0.**
   → importar OSM **no duplicaría a ciegas: hay que cruzar** — OSM trae
   teléfonos que en muchos casos nosotros no tenemos.

### Estado real de las 325 fichas de Moca

| Campo | Vacío | |
|---|---|---|
| `whatsapp` | 325 | **nadie lo usa** |
| `short_description` | 324 | |
| `images` | 324 | |
| `contact_person` | 324 | |
| `email` | 317 | |
| **`phone`** | **301** | **solo 24 con teléfono** |
| `street` | 168 | 48 % con dirección |
| `featured_tier` | 321 | ✅ coherente con los 4 destacados |
| `municipality` | 0 | ✅ las 325 dicen Moca |

> **Escalado**: esto es **un solo municipio** y ya son ~2 000 campos vacíos.
> Ahí el **reporte de §11.1** deja de ser un extra y pasa a ser la **única
> forma** de que la cola sea manejable.

### Pendientes que deja

| # | Qué |
|---|---|
| a | ~~¿Cuántos candidatos cumplen el trío?~~ ✅ **Medido** → arriba. |
| b | ~~¿La dirección se deriva de las coordenadas?~~ ✅ **Sí** → el trío es `nombre + teléfono + punto`. |
| c | ~~Modelo de "pendiente"~~ ✅ **Calculado + `procedencia`**, sin campos nuevos. |
| d | **Duplicados**: el automático publica antes → deduplicación obligatoria **antes** de publicar. |
| e | **Teléfono equivocado publicado es peor que no publicarlo.** El trío es un mínimo, no una garantía. |
| f | ~~¿El teléfono es obligatorio para publicar?~~ ✅ **Sí**, porque es el propio trío. En el círculo de Moca: exigiéndolo entran **17**, no exigiéndolo **101** de las que **84 no se podrían llamar**. |
| g | ~~¿Los candidatos que NO cumplen el trío?~~ ✅ **No se descartan**: entran al reporte por municipio (§11.1) para editarlos y publicarlos a mano. |
| h | ~~Medición de producción~~ ✅ **Hecha** → **131 a 5 km, 322 a 10 km**. |
| i | ~~El reporte de §11.1 no se puede generar hoy~~ ✅ **Endpoint de reporte en el backend**: una consulta, sin inflar el serializer de lista ni hacer 325 llamadas de detalle. |
| j | ~~⚠️ Lo que R1 cuesta (194 de 325, 60 %)~~ ✅ **R1 tal cual: 5 km siempre.** Ese 60 % mide que solo hay datos en **un** municipio, no que el radio esté mal: al poblar los 158 cada uno se busca desde **su propia** cabecera y el descarte se derrumba solo. |

---

## 11. Correctores (R6)

> Aprobado junto con R5. **Dos piezas**: un **reporte de pendientes por
> municipio** y un **formulario de corrector**.

### 11.1 — Reporte de pendientes por municipio

El sistema calcula, **municipio a municipio**, qué le falta a cada ficha, y lo
sirve como **ficha de trabajo** para el corrector asignado.

- **Sale de lo ya decidido**: §9 da el municipio y su cabecera; R5 da el trío y
  los campos pendientes. **Es un cálculo — no hay que guardar nada nuevo.**
- **Contenido**: municipio + cabecera + círculo de 5 km · fichas con pendientes
  agrupadas por **campo faltante** · nombre, punto, procedencia.
- **Formato**: en pantalla o exportable, para **pasárselo a los correctores**.

**Implicación que no se ve a primera vista:** el reporte **por municipio**
implica un **reparto** — si dos correctores toman el mismo municipio →
duplicados (pendiente *d* de R5). Lo natural: **un municipio = un corrector**.

**Tres precisiones que solo salen al ponerlo a funcionar:**

| | |
|---|---|
| **El listado sale del padrón de las 158 cabeceras**, no de lo que ya tenga fichas. Un municipio **sin importar** aparece con `total: 0` — y el cero **es** el trabajo que falta: sin él, el reporte solo contaría lo que ya entra, que es justamente lo contrario de servir para planear. |
| **Lo que no casa con ninguna cabecera se conserva aparte** (incluidas las fichas sin municipio): no poder asignarlas es un pendiente en sí, no un detalle del formato. |
| **Quién lo lee:** el admin, todo; el **colaborador, solo su municipio**, firmado con su token (§11-i). Pedirle `?municipio=` distinto al suyo → `403`; token sin municipio asignado → `400`. El municipio deja de ser «solo informativo» en `Colaborador` — y **solo** para leer: los envíos siguen declarando el suyo propio. |

### 11.2 — Formulario del corrector

| | |
|---|---|
| **Quién** | corrector **contratado** — no el visitante anónimo |
| **Qué hace** | abre su municipio → ve la lista de pendientes → rellena campo a campo |
| **Adónde va** | **envía al admin** → el **admin aprueba y publica** |
| **Alcance** | solo su municipio |

### 11.3 — Dos canales, no uno

| Canal | Quién | Qué hace | Publica |
|---|---|---|---|
| **Corrección pública** *(ya existe)* | visitante **anónimo** | reporta un **error** en una ficha publicada | admin |
| **Formulario de corrector** *(nuevo)* | corrector **contratado** | **rellena lo que falta** | admin |

Los dos caen en **la misma bandeja del admin**. `VISION.md` sigue intacto.

### 11.4 — Decisiones que abre

| # | Qué decidir | Decisión |
|---|---|---|
| i | **Identificación del corrector.** | ✅ **No hay acceso: hay envío.** Herramienta de levantamiento que manda datos al backend. El colaborador no ve nada — ni fichas ajenas, ni admin. **Lo único que lee con su token es su municipio en §11.1** (el reporte de incompletas por municipio), que es lo que le dice qué hacer; todo lo demás le devuelve `403`. |
| j | **Sobre qué trabaja.** | ✅ **Completa → envía → el sistema valida → publica.** La persona **nunca** publica: si el dato no está completo y correcto, no entra. |
| k | **Municipios sin corrector.** | ✅ **Correctores asignados: ninguno por ahora.** El canal se construye completo hoy; el reparto, cuando haya con quién. |

### 11.5 — El canal de envío (decidido)

**Es un canal de escritura, no un acceso.** Quien lo usa no entra al
sistema: nada de login, nada de admin, nada de lectura. Solo empuja.

```
Herramienta de levantamiento (el colaborador recoge los datos)
        │  envía   ← única acción posible
        ▼
POST público validado  +  token que firma el envío
        │
        ├─ validación estructural FALLA
        │    (teléfono malformado · coordenadas fuera del municipio
        │     declarado · sin nombre · duplicado)
        │        → RECHAZADO en la puerta, con el motivo
        │          No llega a quedar "pendiente": no entra.
        │
        ├─ pasa la validación pero LE FALTA EL TRÍO
        │        → queda PENDIENTE en el reporte de ese municipio
        │          (§10-g: no se descarta, se edita a mano)
        │
        └─ pasa la validación Y cumple el trío
                 → PUBLICADO solo
```

**Tres reglas:**

1. **Token por colaborador, no login.** Cada quien recibe una clave que
   **firma** el envío. No abre nada: dice *"esto lo mandó X"*. Sirve para
   auditar y para bloquear a uno sin cerrar a los demás. **Firma ≠
   acceso.**
2. **Validar antes de aceptar, no después.** Un dato malformado no se
   queda en ninguna cola: se rechaza en la puerta con el motivo.
3. **El reporte de §11.1 es la bandeja de edición**, municipio a
   municipio. Ahí se arregla y se publica a mano lo que no llegó a
   cumplir el trío.

**Y lo que NO es:** no hay endpoint de lectura para el colaborador, ni
permiso que le deje consultar el admin. Si mañana hace falta ver cosas,
eso es otro canal y otra decisión.

### 11.6 — Modo «completar la ficha elegida» (decidido)

El reporte de §11.1 decía **qué** faltaba; faltaba poder **arreglarlo**.
Un colaborador en Moca entra con su token, el reporte de su municipio
aparece **de inmediato**, elige una ficha del selector, el formulario
sale **rellenado con lo que ya hay** y con lo faltante **marcado en
amarillo**, rellena y envía → el sistema valida → el selector vuelve con
la lista actualizada, lista para el siguiente.

```
token ✓  →  reporte de MI municipio (solo, sin un clic más)
                 │
                 ├─ selector de las fichas que necesitan completarse
                 ▼
         GET /api/pendientes/?ficha=<id>
                 │  puebla el formulario + lista de faltantes
                 ▼
         POST /api/levantamiento/  { … , ficha: <id> }
                 │
                 ├─ ficha inexistente          → 400 (no existe)
                 ├─ ficha de OTRO municipio    → 403 (a este token no le toca)
                 ├─ pasa, y aún le falta algo  → PENDIENTE, y sigue en el reporte
                 └─ pasa y cumple el trío      → PUBLICADO
                 │
                 ▼
         se limpia la ficha (no el token ni el municipio) y se relee
         el reporte → selector listo para el siguiente
```

**Y por qué así:**

| | |
|---|---|
| **Un solo endpoint, con un `ficha` opcional.** Sin id = alta nueva (como hasta ahora); con id = completar. Misma puerta, misma validación, mismo límite de envíos y misma auditoría para los dos. Abrir una segunda puerta sería otra tasa, otro criterio y otro hueco que vigilar. |
| **Con id NO se cruza a ciegas.** El cruce de §10-d decide por nombre + menos de 300 m, y con 158 municipios eso puede tocar **el negocio de al lado**. Completar es deliberado: quien lo hace ya eligió cuál. |
| **La ficha tiene que ser de SU municipio (§11-i).** La misma llave con la que se **lee** el reporte sirve para **escribir**. Id inexistente → `400` con motivo (mal formado, se rechaza en la puerta); id de otro municipio o token sin municipio → `403`, y **sin** `Envio`: no es un dato malo, es una llave que no abre. |
| **Poblar va aparte: `GET /api/pendientes/?ficha=<id>`.** El listado trae `id, nombre, estado, faltan` — lo justo para decir qué falta. Para **rellenar** hacen falta teléfono, calle, horario, coordenadas… y traerlos de las 148 sería mandar medio municipio a rellenar **uno**. Se pide uno a uno, al elegirlo. |
| **`enriquecer` cubre ahora TODOS los campos del reporte.** Antes solo contacto, dirección y horario: se podía terminar de rellenar una ficha y el reporte la seguía marcando, es decir **no acababa nunca**. Ahora también `nombre`, `punto`, `categoria`, `descripcion` y `estado` — y **siempre sin sobrescribir** lo que ya había (§10-d): una corrección encima del dato existente no es un relleno, es otra decisión. |
| **El estado operativo deja de ser una casilla.** «Está cerrado permanentemente» no podía completar `estado`, que el reporte cuenta como faltante — y eso dejaba fichas trabadas para siempre. Ahora es un selector con los cuatro estados del catálogo; vacío = «sin decidir», que sigue siendo el criterio de siempre para crear. |
| **El desplegable de municipio lo manda la ficha.** Quien eligió la ficha no tiene que reelegir lo que ya está claro; si lo cambia a mano, manda lo que eligió. |
| **Y el `Envio` se anota con la ficha.** `datos.ficha` deja constancia de **cuál** se completó, que es lo que permite juzgar al colaborador concreto (§11.5). |

## 12. Transporte de datos a producción (R5)

Hay **dos bases**: SQLite en local, Postgres gratis en Render. Los 158
municipios se importan **aquí** — OpenStreetMap se consulta desde la
máquina de desarrollo, no desde Render — y a producción llegan por
archivo.

```
aquí                                          en producción
────────────────────────────────              ─────────────────────────────
importar_municipio --todos      Overpass
        │
        ▼
exportar_fichas  ──►  fichas_nacionales.ndjson.gz  ──►  cargar_fichas
                          (el transporte)                  │
                                                          ▼
                                             valida → cruza → crea → publica
```

### Los comandos

| | |
|---|---|
| `manage.py importar_municipio --todos` | Los 158 municipios desde Overpass. **Idempotente**: repetirlo no duplica, enriquece. |
| `manage.py exportar_fichas [salida]` | Una ficha por línea (JSONL, `.gz` si el nombre acaba así). Por defecto `backend/data/fichas_nacionales.ndjson.gz`. |
| `manage.py exportar_fichas --excluir Moca` | **El que se usa para producción.** Moca ya está allá hecha a mano: exportarla solo puede estorbar (§10-d), así que no viaja. |
| `manage.py cargar_fichas <archivo>` | La carga en destino. **Idempotente**: se puede correr dos veces. |
| `manage.py cargar_fichas <archivo> --omitir Moca` | Deja un municipio intacto — el que la base de destino ya tenía trabajado a mano. |

### Por qué un archivo y no `loaddata`

`dumpdata`/`loaddata` viajan por **id primario**, y en el destino esos ids
ya están ocupados por otra cosa: una categoría con `id=5` aquí puede ser
«Tiendas» y allá «Salud», con lo que `loaddata` **pisaría** filas que no
toca. Aquí se viaja por **nombre**, que es como ya cruza §10-d.

El formato vive en `businesses/portar.py`, no en ninguno de los dos
comandos: si viviera en el exportador, quien carga tendría que copiarlo y
un cambio de campo los separaría en silencio. No es un fixture de Django,
es el **mismo diccionario plano** que producen `osm.a_datos` y
`levantamiento._a_datos`.

### Por qué el bucle es uno solo

`importar_municipio` y `cargar_fichas` por fuera no se parecen: uno trae
candidatos de Overpass, otro los trae de un archivo. Por dentro tienen
que hacer **exactamente** lo mismo, y por eso el bucle está en
`businesses/masivo.py` (`Lote`):

```
agregar(datos, cabecera)   valida (§11.5) → exige punto
                           → cabecera más cercana → cruza (§10-d)
publicar()                 §10-f: solo el que cumple el trío
```

Antes ese bucle vivía dentro del importador; sacarlo es lo que hace
posible llevar datos de una base a otra **sin que lo que llegue sea
«casi» lo mismo**. Si cada comando montara el suyo, el día que alguien
cambiara el orden —crear primero y cruzar después— uno de los dos
dejaría de deduplicar y no se enteraría hasta ver dos fichas del mismo
negocio.

### Qué garantiza la carga

| | |
|---|---|
| **No pisa.** | Si el destino ya tiene teléfono, se queda el suyo; el del archivo se ignora (`enriquecer` nunca sobrescribe). |
| **Se puede correr dos veces.** | La segunda no crea nada: `duplicados` en vez de `creados`. Si se corta a mitad, se vuelve a correr. |
| **Una ficha manual no se publica sola.** | Aunque el archivo diga que estaba publicada: quien publica es el admin (VISION.md). |
| **La misma puerta que OSM.** | Lo mal formado se rechaza en la puerta; un punto fuera del círculo de 5 km no entra por venir de un archivo. |
| **`--omitir` para no tocar lo ajeno.** | La base de destino puede tener un municipio trabajado a mano que no debe mezclarse con lo exportado. |

### El paso a producción, tal cual

```bash
# 1. en local, con la importación ya corrida
python manage.py exportar_fichas --excluir Moca
git add backend/data/fichas_nacionales.ndjson.gz
git commit -m "Datos nacionales (157 municipios)"
git push origin main          # autoDeploy redespliega y trae el archivo

# 2. en el Shell de Render (una vez)
python manage.py cargar_fichas data/fichas_nacionales.ndjson.gz

# 3. comprobación
#    GET /api/businesses/?page_size=1  ->  "count" sin los de Moca
```

El paso 2 **no** va en `buildCommand`: se corre una vez a mano. Si
alguna vez hace falta repetirlo, se repite — es idempotente.

### Nota sobre Overpass

`osm.consultar` prueba los tres servidores y, si ninguno contesta, **vuelve
a intentarlo una vez tras 20 s** (`VUELTAS`, `PAUSA_SEGUNDOS`). Un `504`
de Overpass **no** significa que el municipio esté vacío: se distingue
`None` («no hubo red») de `[]` («no hay nada»), y lo primero sale como
`sin_datos` en el resultado, no como municipio sin fichas.

