# 🎮 Color Sort Puzzle - Proyecto Godot 4

> **Juego de puzle de colores para Android** | Versión 1.0 | Noviembre 2026

---

## 📋 Resumen del proyecto

Un juego de clasificación de líquidos por color en tubos, sin texto en el juego (solo iconos y números), listo para publicar en Google Play Store con monetización combinada (anuncios + IAP).

### 🎯 Objetivos

- ✅ **Publicar en Google Play** en 7 días de desarrollo
- ✅ **Cero texto en el juego** - funciona en todos los mercados sin traducir
- ✅ **Monetización**: Anuncios a pantalla completa + anuncios con recompensa + IAP para quitar anuncios
- ✅ **Niveles infinitos** generados proceduralmente con solución garantizada
- ✅ **Mercados**: EE. UU., España, México, Colombia, Argentina, Chile, Perú, República Dominicana

---

## 🛠️ Stack tecnológico

| Tecnología | Versión |
|------------|---------|
| Motor | Godot 4.x (GDScript) |
| Plataforma | Android App Bundle |
| Anuncios | AdMob |
| Compras | Google Play Billing |
| Guardado | Local (`user://save.json`) |

---

## 📁 Estructura del proyecto

```
res://
├── project.godot              # Configuración del proyecto
├── autoload/                  # Autoloads globales
│   ├── save_manager.gd        # Progreso, racha, compras
│   ├── audio_manager.gd       # Música y efectos
│   ├── ads.gd                 # Anuncios (pantalla completa + recompensa)
│   ├── iap.gd                 # Comprar quitar anuncios
│   └── consent.gd             # Consentimiento GDPR (Europa)
├── scenes/                    # Escenas del juego
│   ├── menu.tscn              # Menú principal
│   ├── game.tscn              # Pantalla de partida
│   ├── settings.tscn          # Ajustes
│   └── shop.tscn              # Tienda (quitar anuncios)
├── scripts/                   # Scripts de lógica
│   ├── game_board.gd          # Lógica del tablero
│   ├── tube.gd                # Un tubo: dibujo y animación
│   ├── level_generator.gd     # Generador de niveles
│   ├── level_data.gd          # Recurso con nivel serializado
│   └── daily_challenge.gd     # Reto diario (modo offline)
├── assets/                    # Recursos
│   ├── fonts/                 # Fuentes
│   ├── sfx/                   # Efectos de sonido
│   └── ui/                    # Iconos y UI
└── export/                    # Archivos compilados
```

---

## 📚 Plan de desarrollo (7 días)

### Día 1 — Lógica básica del juego

**Objetivo**: Jugar un nivel completo, ganar, deshacer y reiniciar.

**Tareas**:
- Crear `tube.gd`: dibujar tubo con lista de unidades (color + forma)
- Crear `game_board.gd`: mover unidad de arriba de un tubo a otro
- Detectar nivel completado (todos los tubos vacíos o de un solo color)
- Implementar deshacer (pila de movimientos) y reiniciar

**Terminado cuando**: Puedes jugar un nivel completo sin arte ni sonido.

---

### Día 2 — Generador de niveles + Progreso

**Objetivo**: Niveles infinitos generados automáticamente.

**Tareas**:
- Implementar `level_generator.gd` con algoritmo "resolver y deshacer"
- Serializar niveles con semilla y número (no guardar tablero entero)
- Curva de dificultad progresiva
- `save_manager.gd`: guardar nivel, racha, ajustes

**Algoritmo del generador**:
```gdscript
# 1. Tablero resuelto (cada color entero en su tubo)
# 2. Deshacer el puzle moviendo trozos hacia atrás
# 3. Validaciones para evitar niveles triviales
# 4. Reproducir al revés = solución garantizada
```

**Terminado cuando**: Pasas 50 niveles seguidos generados.

---

### Día 3 — Pulido y sensación

**Objetivo**: El juego se siente bien con el móvil en la mano.

**Tareas**:
- Animación de caída y relleno del tubo: **0.25–0.35 s** (curva suave)
- Sonido al verter, completar tubo, ganar, pulsar
- Vibración corta al completar un tubo
- Paleta de 10 colores + 10 formas distintas
- Tres pantallas: menú, partida, ajustes

**Terminado cuando**: El juego se siente bien sin sonido también.

---

### Día 4 — Anuncios (AdMob)

**Objetivo**: Integrar AdMob con reglas de frecuencia.

**Tareas**:
- Integrar plugin de AdMob para Godot 4
- Configurar IDs de **prueba**
- `ads.gd`: cargar, mostrar pantalla completa, recompensa
- Reglas de frecuencia: cada 3 niveles (después del nivel 3)
- `consent.gd`: formulario de consentimiento para Europa

**Reglas de anuncios**:
- Niveles 1–3: Sin anuncios
- Nivel ≥ 4: Anuncio cada 3 niveles
- Mínimo 90 segundos entre anuncios
- Máximo 6 anuncios por sesión

**Terminado cuando**: Ves un anuncio de prueba funcionando.

---

### Día 5 — Retención + IAP (2 horas extra para depurar)

**Objetivo**: Reto diario, notificaciones y compras.

**Tareas**:
- Reto diario: semilla basada en fecha local (modo offline)
- Notificación local diaria (activable en ajustes)
- Integrar Google Play Billing para quitar anuncios
- `iap.gd`: consultar compras al arrancar, lanzar compra
- Pantalla de tienda con botón y precio localizado

**Precios por región**:
| País | Precio |
|------|--------|
| Estados Unidos | $3.99 |
| España / zona euro | €2.99 |
| Latinoamérica | $1.99 |

**Terminado cuando**: La compra funciona y sobrevive al reinicio.

---

### Día 6 — La tienda

**Objetivo**: Ficha completa en Play Store.

**Tareas**:
- Icono 512×512 + icono adaptativo
- Gráfico destacado 1024×500
- 6 capturas 1080×1920 con texto en inglés
- Vídeo de 15 s (opcional)
- Ficha en inglés, español y portugués
- Política de privacidad + formulario de seguridad

**Palabras clave**: `color sort`, `water sort`, `ball sort`, `sort puzzle`, `brain puzzle`

---

### Día 7 — Pruebas + Lanzamiento

**Objetivo**: Cero errores, publicar en prueba cerrada.

**Tareas**:
- Instalar en 10 probadores (entorno interno de Play)
- Probar: primer arranque, 10 niveles, atascarse, comprar
- Corregir errores y bloquear el código
- Publicar en prueba cerrada con los 10 probadores
- Lanzamiento suave en 2 países pequeños

---

## 📊 Métricas de éxito (a 30 días)

| Métrica | Objetivo |
|---------|----------|
| Retención día 1 | ≥ 30 % |
| Retención día 7 | ≥ 10 % |
| Sesiones por usuario | ≥ 3 |
| Anuncios por usuario activo | 4–8 |
| Caída de la app | ≥ 99 % sin errores |
| Conversión ficha (visitas → instalaciones) | ≥ 25 % |

---

## 💰 Ingresos esperados (20,000 descargas)

| Fuente | Cálculo | Total |
|--------|---------|-------|
| Anuncios a pantalla completa | 90,000 vistas × $5.20/mil | $468 |
| Anuncios con recompensa | 36,000 vistas × $9.75/mil | $351 |
| Compras de quitar anuncios | 159 compras | $410 |
| **Total** | | **≈ $1,230** |

---

## 🚀 Instalación y configuración

### 1. Instalar Godot 4

1. Ve a [godotengine.org/download](https://godotengine.org/download)
2. Descarga la versión **stable 4.x** (recomendado: 4.3 LTS)
3. Instala el editor
4. Abre Godot por primera vez

### 2. Configurar proyecto para Android

```bash
# En el editor de Godot:
Proyecto → Exportar → Agregar plataforma → Android
Ajustes → Exportación → Android → Activado
```

### 3. Cuentas necesarias

#### Google Play Console
- Costo: $25 USD único (verificación de identidad)
- [play.google.com/console](https://play.google.com/console)
- Crea cuenta → Sube APK/AAB → Publicar

#### AdMob
- [adsense.google.com](https://adsense.google.com)
- Genera App ID: `ca-app-pub-XXXXXXXXXXXXXXXX~YYYYYYYYYY`
- Genera IDs de anuncios:
  - Interstitial: `ca-app-pub-XXXXXXXXXXXXXXXX/ZZZZZZZZ`
  - Rewarded: `ca-app-pub-XXXXXXXXXXXXXXXX/AAAAAAA`

#### Entorno interno de pruebas
- En Play Console → Pruebas → Entorno interno
- Invita hasta 10 probadores por email
- Sube AAB → Probadores reciben notificación

---

## 📋 Lista de verificación pre-lanzamiento

```
□ Godot 4 instalado y configurado para Android
□ Cuenta Play Console creada
□ IDs de AdMob generados y configurados
□ Entorno interno con 10 probadores
□ Política de privacidad publicada
□ Formulario de seguridad de datos completado
□ Niveles 1-30 probados (sin niveles triviales)
□ Anuncios funcionando con IDs de prueba
□ IAP funcionando y restaurando al reinstalar
□ Reto diario con modo offline
□ Animaciones 0.25–0.35 s
□ Consentimiento GDPR antes del primer anuncio
□ Iconos y capturas listos
□ Ficha en inglés, español, portugués
```

---

## 🛡️ Reglas de oro (no negociables)

1. **Nada de anuncios en la primera sesión ni primeros 2 minutos**
2. **Nunca interrumpir una partida en curso** - solo entre niveles
3. **El anuncio con recompensa se ofrece, no se impone**
4. **Nunca poner un anuncio después de una derrota**
5. **Solo IDs de prueba durante el desarrollo** - nunca pulsar anuncios reales propios

---

## ⚠️ Riesgos y mitigación

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| IAP no funciona en Godot | Media | 2 horas extra en Día 5; publicar sin IAP en 1.1 |
| Género saturado | Alta | Ficha en inglés + 14 días de vídeos diarios |
| Retraso por probadores | Alta | Entorno interno de Play (hasta 10 probadores) |
| Suspensión AdMob por clics propios | Baja | Solo IDs de prueba, nunca pulsar anuncios reales |

---

## 📞 Contacto y soporte

- **Motor**: [Godot Engine](https://godotengine.org)
- **AdMob**: [Google AdMob](https://admob.google.com)
- **Play Console**: [Google Play Console](https://play.google.com/console)

---

## 📜 Licencia

Este proyecto es propiedad del desarrollador. Código fuente disponible bajo licencia personal.

---

## 🎯 Definición de "terminado"

El proyecto está terminado cuando, en un móvil real:

- [ ] Se instala desde Play y arranca sin errores
- [ ] Se juegan 10 niveles seguidos (ninguno imposible ni trivial)
- [ ] Al atascarse, se ofrece el anuncio con recompensa
- [ ] El anuncio a pantalla completa respeta las reglas de frecuencia
- [ ] La compra de quitar anuncios funciona y se restaura al reinstalar
- [ ] El progreso se conserva al cerrar y abrir
- [ ] El reto diario aparece con la fecha correcta (modo offline)
- [ ] La app no pide permisos innecesarios
- [ ] La ficha está completa en 3 idiomas
- [ ] La política de privacidad es accesible

---

## 📅 Calendario real hasta producción

| Semana | Qué pasa |
|--------|----------|
| **Semana 1** | Desarrollo (días 1–7) |
| **Semana 2–3** | Prueba cerrada con 10 probadores durante 14 días |
| **Semana 3** | Recoger datos de retención, corregir errores |
| **Semana 4** | Publicación en producción + campaña de vídeos |

> Si la cuenta es **de organización**, el requisito de los 10 probadores no aplica y se puede publicar el día 8.

---

*Fin del README*
