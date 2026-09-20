from django.contrib import admin
from .models import BusinessLocation


class BusinessLocationAdmin(admin.ModelAdmin):
    list_display = ['business', 'address', 'city', 'state', 'country', 'latitude', 'longitude']
    search_fields = ['business__name', 'address', 'city']
    list_filter = ['city', 'state', 'country']
    raw_id_fields = ['business']
    list_per_page = 25
    readonly_fields = ['business']


# NO se registra con admin.site -> no aparece en el sidebar
# Se gestiona como inline dentro de Negocios
