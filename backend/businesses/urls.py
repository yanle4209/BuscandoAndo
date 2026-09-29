from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'businesses', views.BusinessViewSet, basename='business')
# POST publico (formulario "Corregir"); el resto, solo staff.
router.register(r'corrections', views.CorrectionViewSet, basename='correction')

urlpatterns = [
    path('', include(router.urls)),
]
