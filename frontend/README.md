# Frontend (React + Vite)

La web de BuscandoAndo: React 19 + Vite, con Leaflet para el mapa.
Habla con el backend Django de `../backend` por los mismos endpoints
(la API está descrita en el README de la raíz).

## Desarrollo

```bash
npm install
npm run dev
```

El dev server (`:5173`) tiene proxy de `/api` y `/media` hacia el
backend en `127.0.0.1:8000` (`vite.config.js`), así que levanta el
backend aparte para tener datos.

## Comandos

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con HMR |
| `npm run lint` | Oxlint (sin errores es requisito del CI) |
| `npm run build` | Build de producción → `dist/` |
| `npm run preview` | Vista previa del build |

## Cómo está montado

- **Rutas lazy** (`App.jsx`): Home, BusinessDetail y Levantamiento
  cargan bajo demanda; Leaflet solo se monta cuando hay mapa
  (`MapView`), con su propio `Suspense`.
- **`Home.jsx`** es la máquina de estados de `DISENO.md` §1: punto
  activo (GPS o cabecera municipal), refresco con throttle de 30 s,
  búsqueda a 5 km y banner de fase.
- **`Levantamiento.jsx`** es la herramienta de campo (§11): entra con
  token de colaborador, ve el reporte de su municipio y envía fichas.
- **Sin CDNs externos**: todo (incluido Leaflet) va empaquetado, que
  es lo que exige la CSP del backend.
- `public/robots.txt` **no es decorado**: es el respaldo del build que
  lee la vista backend cuando la fila de la BD está en blanco
  (`views.py` → `_robots_efectivo`). Borrarlo rompe el test
  `test_fila_en_blanco_vuelve_al_build`.

Ver `../DISENO.md` para las decisiones de diseño y
`../AUDITORIA_SEGURIDAD.md` / `../AUDITORIA_PRE_LANZAMIENTO.md` para
las auditorías.
