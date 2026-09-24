from django import forms
from django.contrib import admin
from django.forms import BaseInlineFormSet
from .models import BusinessHours


DAYS_OF_WEEK = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


class BusinessHoursForm(forms.ModelForm):
    class Meta:
        model = BusinessHours
        fields = ['day', 'open_time', 'close_time', 'is_closed', 'is_holiday']
        widgets = {
            'day': forms.Select(attrs={'style': 'width: 100%;'}),
            'open_time': forms.TimeInput(
                attrs={'type': 'time', 'style': 'width: 100%;', 'step': '60'},
                format='%H:%M',
            ),
            'close_time': forms.TimeInput(
                attrs={'type': 'time', 'style': 'width: 100%;', 'step': '60'},
                format='%H:%M',
            ),
        }


class PrePopulatedHoursFormSet(BaseInlineFormSet):
    """Formset que pre-pobla los 7 días de la semana."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si no hay objetos guardados, pre-poblar los días
        if not self.instance or not self.instance.pk or not self.instance.hours.exists():
            for i, form in enumerate(self.forms):
                if i < len(DAYS_OF_WEEK) and not form.instance.pk:
                    form.initial['day'] = DAYS_OF_WEEK[i]


class BusinessHoursInline(admin.TabularInline):
    model = BusinessHours
    form = BusinessHoursForm
    formset = PrePopulatedHoursFormSet
    extra = 7
    max_num = 7
    fields = ['day', 'open_time', 'close_time', 'is_closed', 'is_holiday']
    ordering = ['day']


class BusinessHoursAdmin(admin.ModelAdmin):
    list_display = ['business', 'day', 'open_time', 'close_time', 'is_closed', 'is_holiday']
    list_filter = ['day', 'is_closed', 'is_holiday']
    raw_id_fields = ['business']
    list_per_page = 25
    ordering = ['business', 'day']
    readonly_fields = ['business']


# NO se registra con admin.site -> no aparece en el sidebar
# Se gestiona como inline dentro de Negocios
