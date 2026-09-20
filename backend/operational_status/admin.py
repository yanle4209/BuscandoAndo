from django.contrib import admin
from .models import OperationalStatus


class OperationalStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'color', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    list_per_page = 10
    ordering = ['order']


# NO se registra con admin.site -> no aparece en el sidebar
# Se gestiona desde los filtros de Negocios
