"""
Feriados oficiales de República Dominicana.
Se usa para auto-detectar días de fiesta en los horarios.
"""
from django.utils import timezone


# Feriados fijos (día y mes)
FIXED_HOLIDAYS = [
    (1, 1, "Año Nuevo"),
    (1, 21, "Día de los Próceres"),
    (1, 26, "Día de la Altagracia"),
    (2, 27, "Día de la Independencia"),
    (5, 1, "Día del Trabajo"),
    (8, 16, "Día de la Restauración"),
    (9, 24, "Día de las Mercedes"),
    (11, 6, "Día de la Constitución"),
    (12, 25, "Navidad"),
]


def is_holiday(dt=None):
    """Verifica si una fecha es feriado en República Dominicana."""
    if dt is None:
        dt = timezone.localdate()

    for month, day, name in FIXED_HOLIDAYS:
        if dt.month == month and dt.day == day:
            return name
    return None
