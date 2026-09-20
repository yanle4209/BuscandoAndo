from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for BuscandoAndo."""

    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Cliente'
        BUSINESS_OWNER = 'business_owner', 'Dueño de Negocio'
        ADMIN = 'admin', 'Administrador'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )
    phone = models.CharField(max_length=20, blank=True, default='')
    avatar = models.FileField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.username}"

    @property
    def is_business_owner(self):
        return self.role == self.Role.BUSINESS_OWNER

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER
