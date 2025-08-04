from django.db import models
from django.conf import settings
from core.models import BaseModel
from simple_history.models import HistoricalRecords

class Business(BaseModel):
    nombre = models.CharField(max_length=128)
    rut = models.CharField(max_length=20, unique=True)
    dueno = models.ForeignKey('accounts.Perfil', on_delete=models.CASCADE, related_name="empresas")
    email = models.EmailField()
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=200)

    history = HistoricalRecords()

    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = 'Negocio'
        verbose_name_plural = 'Negocios'


class BusinessConfig(BaseModel):
    """Configuración de negocio"""
    
    # Relación con el usuario (cada usuario puede tener su propia configuración)
    user = models.ForeignKey('accounts.Perfil', on_delete=models.CASCADE, related_name='business_config')
    
    # Configuración general
    default_view_mode = models.CharField(
        max_length=20, 
        choices=[('standard', 'Estándar'), ('visual', 'Visual')],
        default='standard',
        help_text='Modo de vista predeterminado al abrir POS'
    )
    
    class Meta:
        verbose_name = 'Configuración de negocio'
        verbose_name_plural = 'Configuraciones de negocio'