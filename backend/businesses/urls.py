from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'businesses', views.BusinessViewSet, basename='business')

urlpatterns = [
    path('', include(router.urls)),
]
