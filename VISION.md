# Visión del Backend - BuscandoAndo

## Tarjeta de Resultado (Cada entrada)
Cada tarjeta debe mostrar:
- **Nombre** del negocio/servicio
- **Dirección**
- **Teléfono**
- **WhatsApp** (opcional)
- **Correo** (opcional)
- **Horario de atención**
- **Estado del negocio:** Abierto | Cerrado | Cerrado Permanentemente | Por Cerrar
- **Mini mapa** con ubicación

## Flujo de Estados (Publicación)
```
[En Revisión] → [Publicado]
                [Cancelado]
```
- Estado inicial: **"En Revisión"**
- Solo se publica cuando el admin cambia a **"Publicado"**
- Si se rechaza: **"Cancelado"**
- Las entradas en "En Revisión" NO se muestran públicamente

## Edición
- Todo se edita desde el **Admin de Django**
- Todos los campos son editables manualmente

## Poblado Inicial
- Importar vía JSON / API / CSV
- Script de seed para carga inicial
