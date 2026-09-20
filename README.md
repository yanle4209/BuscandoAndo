# BuscandoAndo 🔍

Plataforma de búsqueda de servicios y negocios. Hecha con Django + React.

## Backend (Django + DRF)

### Estructura
```
backend/
├── config/          # Configuración de Django
├── accounts/        # App de usuarios (registro, login, perfil)
├── businesses/      # App de negocios, categorías, reseñas, favoritos
├── manage.py
├── seed_data.py
└── requirements.txt
```

### Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/accounts/register/` | Registrar usuario |
| POST | `/api/accounts/login/` | Iniciar sesión |
| GET/PUT | `/api/accounts/profile/` | Ver/editar perfil |
| GET | `/api/categories/` | Listar categorías |
| GET/POST | `/api/businesses/` | Listar/crear negocios |
| GET | `/api/businesses/<slug>/` | Detalle de negocio |
| GET/POST | `/api/reviews/` | Listar/crear reseñas |
| GET/POST | `/api/favorites/` | Listar/agregar favoritos |
| GET | `/api/search/?q=...` | Buscar negocios |

### Filtros de búsqueda (en `/api/businesses/`)
- `?search=restaurante` — Buscar por nombre/descripción/ciudad
- `?category=restaurantes` — Filtrar por categoría
- `?city=bogota` — Filtrar por ciudad
- `?featured=true` — Solo destacados

### Instalación
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Superusuario (desarrollo)
- Usuario: `admin`
- Contraseña: `admin123`

## Frontend (React) — Próximamente
