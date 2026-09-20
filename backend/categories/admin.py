from django.contrib import admin
from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_parent', 'icon', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    list_per_page = 25
    ordering = ['parent__name', 'name']

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent', 'icon', 'description')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )

    def get_parent(self, obj):
        return obj.parent.name if obj.parent else '-'
    get_parent.short_description = 'Categoría padre'
    get_parent.admin_order_field = 'parent__name'
