# Scripts de un solo uso (NO se despliegan)

Estos scripts se ejecutaron una vez para arreglar/importar datos y ya no
deben correr contra producción. Están **fuera del repo** (esta carpeta
está en `.gitignore`), así que **no viajan a Render ni se ejecutan nunca
en el servidor** — sobre todo `clear_all_businesses.py`, que borra la BD
entera sin confirmación.

> Antes vivían en la raíz de `backend/`, donde un `python
> clear_all_businesses.py` en el Shell de Render habría vaciado la base.

## Cómo ejecutarlos (si acaso)

Como ya no están en la raíz, se ejecutan como módulo desde `backend/`:

```bash
cd backend
DB_PASSWORD=tu_password_local python -m scripts_antiguos.nombre_del_script
```

En PowerShell:

```powershell
cd backend
$env:DB_PASSWORD = "tu_password_local"
python -m scripts_antiguos.nombre_del_script
```

`export_data.py` ya **no lleva la contraseña escrita dentro**: la lee del
entorno (`DB_PASSWORD`), igual que `config/settings.py`.

## Inventario

| Script | Qué hacía |
|---|---|
| `clear_all_businesses.py` | ⚠️ **Borrado total** de negocios y relacionados, sin confirmación |
| `export_data.py` | Volcado Postgres → `initial_data.json` |
| `import_osm.py`, `import_businesses.py` | Importación inicial desde OSM |
| `seed_data.py`, `seed_businesses.py`, `seed_restaurants.py` | Siembra de datos de prueba |
| `fix_tiers*.py`, `fix_featured.py`, `fix_locations.py`, `fix_old_locations.py` | Correcciones puntuales de tier/destacados/ubicaciones |
| `check_*.py`, `list_tiers.py`, `all_moca.py` | Consultas de diagnóstico |
| `add_*_images.py`, `assign_tiers.py` | Carga puntual de imágenes y asignación de tiers |
| `_check_imgs.py` | Diagnóstico de imágenes contra `db.sqlite3` local |

La carga de fichas oficial **no** está aquí: es el management command
`python manage.py cargar_fichas data/fichas_nacionales.ndjson.gz`.
