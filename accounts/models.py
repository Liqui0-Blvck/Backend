from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    def _create_user(self, email, password=None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Usuario personalizado que usa email como identificador único y grupos para roles"""
    # Usamos únicamente grupos de Django para roles
    # No se definen constantes ni métodos relacionados a 'role'.
    username = None
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=30, null=False, blank=False)
    second_name = models.CharField(_('second name'), max_length=30, null=True, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, null=False, blank=False)
    second_last_name = models.CharField(_('second last name'), max_length=30, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()
    

    def __str__(self):
        return self.email

class Perfil(models.Model):
    """Perfil extendido para el usuario con información adicional"""
    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE, related_name='perfil')
    phone = models.CharField(_('phone number'), max_length=15, null=True, blank=True)
    rut = models.CharField(_('tax ID'), max_length=15, unique=True, null=True, blank=True)
    business = models.ForeignKey('business.Business', on_delete=models.SET_NULL, related_name='miembros', null=True, blank=True)
    
    class Meta:
        verbose_name = _('profile')
        verbose_name_plural = _('profiles')

    def __str__(self):
        return f"Perfil de {self.user.email}"


COLOR_CHOICES = [
    ('inherit', 'Inherit'),
    ('current', 'Current'),
    ('transparent', 'Transparent'),
    ('black', 'Black'),
    ('white', 'White'),
    ('zinc', 'Zinc'),
    ('red', 'Red'),
    ('darkred', 'Dark Red'),
    ('tomato', 'Tomato'),
    ('salmon', 'Salmon'),
    ('orange', 'Orange'),
    ('gold', 'Gold'),
    ('yellow', 'Yellow'),
    ('lime', 'Lime'),
    ('green', 'Green'),
    ('darkgreen', 'Dark Green'),
    ('turquoise', 'Turquoise'),
    ('cyan', 'Cyan'),
    ('skyblue', 'Sky Blue'),
    ('blue', 'Blue'),
    ('navy', 'Navy'),
    ('indigo', 'Indigo'),
    ('purple', 'Purple'),
    ('magenta', 'Magenta'),
    ('pink', 'Pink'),
    ('crimson', 'Crimson'),
    ('amber', 'Ambar'),
    ('emerald', 'Esmeralda'),
    ('violet', 'Violeta'),
]



DARK_MODE = [
    ('dark', 'Dark'),
    ('light', 'Light'),
]
    
class ConfiguracionUsuario(models.Model):
    perfil = models.OneToOneField('accounts.Perfil', on_delete=models.CASCADE, related_name='configuracion')
    notificaciones = models.BooleanField(default=True)
    privacidad = models.BooleanField(default=True)
    estilo_aplicacion = models.CharField(max_length=20, choices=DARK_MODE, default='light')
    color_aplicacion = models.CharField(max_length=20, choices=COLOR_CHOICES, default='white')

    def __str__(self):
        return self.perfil.user.first_name