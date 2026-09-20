from django.contrib import admin
from .models import BusinessImage


class BusinessImageInline(admin.TabularInline):
    model = BusinessImage
    extra = 0
    max_num = 5
    fields = ['image', 'caption', 'order']
    ordering = ['order']
