from django.db import models
from businesses.models import Business


class BusinessHours(models.Model):
    """Horario de atención por día de la semana."""

    class DayOfWeek(models.TextChoices):
        MONDAY = 'Lunes', 'Lunes'
        TUESDAY = 'Martes', 'Martes'
        WEDNESDAY = 'Miércoles', 'Miércoles'
        THURSDAY = 'Jueves', 'Jueves'
        FRIDAY = 'Viernes', 'Viernes'
        SATURDAY = 'Sábado', 'Sábado'
        SUNDAY = 'Domingo', 'Domingo'

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='hours',
        verbose_name='Negocio',
    )
    day = models.CharField(
        max_length=10,
        choices=DayOfWeek.choices,
        verbose_name='Día',
    )
    open_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Hora de apertura',
    )
    close_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Hora de cierre',
    )
    is_closed = models.BooleanField(
        default=False,
        verbose_name='Cerrado este día',
    )

    class Meta:
        verbose_name = 'Horario'
        verbose_name_plural = 'Horarios'
        ordering = ['day']
        unique_together = ['business', 'day']

    def __str__(self):
        if self.is_closed:
            return f"{self.business.name} - {self.day}: Cerrado"
        return f"{self.business.name} - {self.day}: {self.open_time} - {self.close_time}"
