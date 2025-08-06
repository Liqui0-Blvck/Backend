from django.db import models
from core.models import BaseModel
from simple_history.models import HistoricalRecords
from django.utils.translation import gettext_lazy as _

class BillingInfo(BaseModel):
    """
    Modelo para almacenar información de facturación de los clientes.
    Esta información se utiliza para generar facturas y boletas.
    """
    cliente = models.OneToOneField('Customer', on_delete=models.CASCADE, related_name='billing_info')
    
    # Información fiscal
    razon_social = models.CharField(max_length=200, verbose_name=_('Razón Social'))
    rut_facturacion = models.CharField(max_length=20, verbose_name=_('RUT para facturación'))
    giro = models.CharField(max_length=200, verbose_name=_('Giro Comercial'))
    
    # Dirección de facturación
    direccion_facturacion = models.CharField(max_length=255, verbose_name=_('Dirección de Facturación'))
    comuna = models.CharField(max_length=100, verbose_name=_('Comuna'))
    ciudad = models.CharField(max_length=100, verbose_name=_('Ciudad'))
    region = models.CharField(max_length=100, verbose_name=_('Región'))
    
    # Contacto para facturación
    contacto_nombre = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Nombre de Contacto'))
    contacto_email = models.EmailField(blank=True, null=True, verbose_name=_('Email de Contacto'))
    contacto_telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Teléfono de Contacto'))
    
    # Preferencias de facturación
    TIPO_DOCUMENTO_CHOICES = [
        ('factura', _('Factura Electrónica')),
        ('boleta', _('Boleta Electrónica')),
        ('guia', _('Guía de Despacho')),
    ]
    tipo_documento_preferido = models.CharField(
        max_length=20, 
        choices=TIPO_DOCUMENTO_CHOICES,
        default='factura',
        verbose_name=_('Tipo de Documento Preferido')
    )
    
    # Condiciones de pago preferidas
    condiciones_pago = models.CharField(max_length=200, blank=True, null=True, 
                                       verbose_name=_('Condiciones de Pago'),
                                       help_text=_('Ej: 30 días, Contado, etc.'))
    
    # Notas adicionales para facturación
    notas_facturacion = models.TextField(blank=True, null=True, 
                                        verbose_name=_('Notas de Facturación'),
                                        help_text=_('Instrucciones especiales para facturación'))
    
    # Campos de auditoría
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Facturación: {self.razon_social} ({self.cliente.nombre})"
    
    class Meta:
        verbose_name = _('Información de Facturación')
        verbose_name_plural = _('Información de Facturación')
