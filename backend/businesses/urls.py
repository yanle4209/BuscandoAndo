from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'businesses', views.BusinessViewSet, basename='business')
# POST publico (formulario "Corregir"); el resto, solo staff.
router.register(r'corrections', views.CorrectionViewSet, basename='correction')

urlpatterns = [
    path('', include(router.urls)),
    # Las 158 cabeceras municipales del pais. Un dato, dos usos (DISENO.md R3):
    # ancla de los circulos de 5 km cuando no hay GPS, y fuente del selector
    # manual de municipio.
    path('cabeceras/', views.cabeceras, name='cabeceras'),
]
