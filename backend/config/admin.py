from django.contrib import admin

# Personalizar textos del admin estándar
admin.site.site_header = 'BuscandoAndo - Panel de Administracion'
admin.site.site_title = 'BuscandoAndo Admin'
admin.site.index_title = 'Gestion de Negocios y Servicios'
admin.site.site_url = '/'

# El enlace a la herramienta de levantamiento, lo primero del inicio:
# admin/buscandoando_index.html extiende el indice de Django y pone el
# panel (enlace + boton de compartir) encima de la lista de aplicaciones.
admin.site.index_template = 'admin/buscandoando_index.html'
