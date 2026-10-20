from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .levantamiento import levantamiento

router = DefaultRouter()
router.register(r'businesses', views.BusinessViewSet, basename='business')
# POST publico (formulario "Corregir"); el resto, solo staff.
router.register(r'corrections', views.CorrectionViewSet, basename='correction')

urlpatterns = [
    path('', include(router.urls)),
    # Las cabeceras municipales de las provincias de fase (el padron
    # completo vive en geografia). Un dato, dos usos (DISENO.md R3):
    # ancla de los circulos de 5 km cuando no hay GPS, y fuente del
    # selector manual de municipio.
    path('cabeceras/', views.cabeceras, name='cabeceras'),
    # Aviso de lista de espera del banner de fuera de fase (FASE1):
    # solo suma la metrica aviso_interes, sin datos del usuario.
    path('interes/', views.interes, name='interes'),
    # Reporte de pendientes por municipio (DISENO.md 11.1): la ficha de
    # trabajo del editor. Solo staff.
    path('pendientes/', views.pendientes, name='pendientes'),
    # Canal de envio del levantamiento (DISENO.md 11.5). Sin login: la
    # puerta es el token del colaborador, y quien envia no publica.
    path('levantamiento/', levantamiento, name='levantamiento'),
]
