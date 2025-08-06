from django.db import models
from core.models import BaseModel
from simple_history.models import HistoricalRecords
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class BankAccount(BaseModel):
    """
    Modelo para almacenar cuentas bancarias del negocio para recibir transferencias.
    Estas cuentas se mostrarán como opciones en la API para que los clientes puedan realizar pagos.
    """
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='bank_accounts')
    
    # Información del banco
    BANK_CHOICES = [
        ('banco_estado', _('Banco Estado')),
        ('banco_santander', _('Banco Santander')),
        ('banco_chile', _('Banco de Chile')),
        ('banco_bci', _('Banco BCI')),
        ('banco_scotiabank', _('Banco Scotiabank')),
        ('banco_itau', _('Banco Itaú')),
        ('banco_security', _('Banco Security')),
        ('banco_falabella', _('Banco Falabella')),
        ('banco_ripley', _('Banco Ripley')),
        ('otro', _('Otro')),
    ]
    banco = models.CharField(max_length=50, choices=BANK_CHOICES, verbose_name=_('Banco'))
    otro_banco = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Otro Banco'),
                                 help_text=_('Completar solo si seleccionó "Otro" en el campo Banco'))
    
    # Información de la cuenta
    ACCOUNT_TYPE_CHOICES = [
        ('corriente', _('Cuenta Corriente')),
        ('vista', _('Cuenta Vista')),
        ('ahorro', _('Cuenta de Ahorro')),
        ('rut', _('Cuenta RUT')),
    ]
    tipo_cuenta = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name=_('Tipo de Cuenta'))
    numero_cuenta = models.CharField(max_length=30, verbose_name=_('Número de Cuenta'))
    
    # Titular de la cuenta
    titular = models.CharField(max_length=200, verbose_name=_('Nombre del Titular'))
    rut_titular = models.CharField(max_length=20, verbose_name=_('RUT del Titular'))
    email_notificaciones = models.EmailField(verbose_name=_('Email para Notificaciones'),
                                           help_text=_('Email donde se recibirán notificaciones de transferencias'))
    
    # Estado de la cuenta
    activa = models.BooleanField(default=True, verbose_name=_('Cuenta Activa'),
                                help_text=_('Desactivar para que no aparezca como opción de pago'))
    
    # Orden de visualización (para mostrar primero las cuentas preferidas)
    orden = models.PositiveSmallIntegerField(default=0, verbose_name=_('Orden de Visualización'),
                                           help_text=_('Las cuentas se mostrarán ordenadas de menor a mayor'))
    
    # Notas internas
    notas = models.TextField(blank=True, null=True, verbose_name=_('Notas Internas'))
    
    # Campos de fecha
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name=_('Fecha de Creación'))
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name=_('Última Actualización'))
    
    # Campos de auditoría
    history = HistoricalRecords()
    
    def __str__(self):
        banco_display = self.get_banco_display() if self.banco != 'otro' else self.otro_banco
        return f"{banco_display} - {self.get_tipo_cuenta_display()} - {self.numero_cuenta[-4:]} ({self.titular})"
    
    @property
    def banco_nombre(self):
        """Retorna el nombre del banco, ya sea de las opciones predefinidas o el campo 'otro_banco'"""
        if self.banco == 'otro':
            return self.otro_banco or 'Otro banco'
        return self.get_banco_display()
    
    class Meta:
        verbose_name = _('Cuenta Bancaria')
        verbose_name_plural = _('Cuentas Bancarias')
        ordering = ['orden', 'banco', 'id']
