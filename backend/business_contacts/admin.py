from django.contrib import admin
from .models import BusinessContact


class BusinessContactAdmin(admin.ModelAdmin):
    list_display = ['business', 'phone', 'whatsapp', 'email', 'website']
    search_fields = ['business__name', 'phone', 'whatsapp', 'email']
    raw_id_fields = ['business']
    list_per_page = 25
    readonly_fields = ['business']


# NO se registra con admin.site -> no aparece en el sidebar
# Se gestiona como inline dentro de Negocios
