"""
Feriados oficiales de República Dominicana.
Se usa para auto-detectar días de fiesta en los horarios.
"""
from datetime import date


# Feriados fijos (día y mes固定的)
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

# Días de la semana en español -> índice (0=Lunes, 6=Domingo)
DAY_NAME_TO_INDEX = {
    'Lunes': 0,
    'Martes': 1,
    'Miércoles': 2,
    'Jueves': 3,
    'Viernes': 4,
    'Sábado': 5,
    'Domingo': 6,
}


def is_holiday(dt=None):
    """Verifica si una fecha es feriado en República Dominicana."""
    if dt is None:
        dt = date.today()

    for month, day, name in FIXED_HOLIDAYS:
        if dt.month == month and dt.day == day:
            return name
    return None


def get_holiday_for_day(day_name, dt=None):
    """
    Verifica si un día de la semana (ej: 'Lunes') coincide con un feriado
    en la fecha dada (o hoy por defecto).
    """
    if dt is None:
        dt = date.today()

    today_index = dt.weekday()  # 0=Lunes
    target_index = DAY_NAME_TO_INDEX.get(day_name)
    if target_index is None:
        return None

    # Calcular la fecha del día indicado en la semana actual
    diff = target_index - today_index
    target_date = date.fromordinal(dt.toordinal() + diff)

    return is_holiday(target_date)


def get_all_holidays_for_current_week(dt=None):
    """
    Retorna un dict con los días de la semana que son feriados esta semana.
    {day_name: holiday_name, ...}
    """
    if dt is None:
        dt = date.today()

    result = {}
    for day_name in DAY_NAME_TO_INDEX:
        holiday = get_holiday_for_day(day_name, dt)
        if holiday:
            result[day_name] = holiday
    return result


def get_holidays_for_year(year=None):
    """Retorna todos los feriados de un año."""
    if year is None:
        year = date.today().year

    holidays = []
    for month, day, name in FIXED_HOLIDAYS:
        try:
            dt = date(year, month, day)
            day_name = ['Lunes', 'Martes', 'Miércoles', 'Jueves',
                        'Viernes', 'Sábado', 'Domingo'][dt.weekday()]
            holidays.append({
                'date': dt,
                'day_name': day_name,
                'name': name,
            })
        except ValueError:
            pass
    return holidays
