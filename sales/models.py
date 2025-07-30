from django.db import models
import uuid
from datetime import datetime
from decimal import Decimal
from core.models import BaseModel
from simple_history.models import HistoricalRecords
from django.utils.translation import gettext_lazy as _
# No importar modelos de otras apps arriba para evitar ciclos

class Customer(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    rut = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    frecuente = models.BooleanField(default=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    # Campos para manejo de crédito
    credito_activo = models.BooleanField(default=False, verbose_name=_('Crédito Activo'))
    limite_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True, verbose_name=_('Límite de Crédito'))
    cliente_desde = models.DateField(auto_now_add=True, null=True, blank=True, verbose_name=_('Cliente Desde'))

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nombre} ({self.rut}){' [Frecuente]' if self.frecuente else ''}"
    
    @property
    def saldo_actual(self):
        """Calcula el saldo actual del cliente basado en ventas a crédito no pagadas"""
        # Suma de todas las ventas a crédito no pagadas
        ventas_credito = self.sales.filter(metodo_pago='credito', pagado=False).aggregate(
            total=models.Sum('total')
        )['total'] or Decimal('0.00')
        
        return ventas_credito
    
    @property
    def credito_disponible(self):
        """Calcula el crédito disponible para el cliente"""
        if not self.credito_activo or not self.limite_credito:
            return Decimal('0.00')
        return max(self.limite_credito - self.saldo_actual, Decimal('0.00'))
    
    @property
    def pagos_pendientes(self):
        """Retorna el número de pagos pendientes"""
        return self.sales.filter(metodo_pago='credito', pagado=False).count()
    
    @property
    def total_pagado(self):
        """Retorna el total pagado por el cliente"""
        pagos = self.pagos.aggregate(total=models.Sum('monto'))['total'] or Decimal('0.00')
        return pagos

class CustomerPayment(BaseModel):
    """
    Modelo para registrar pagos realizados por clientes, especialmente para ventas a crédito.
    """
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    cliente = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='pagos')
    METODO_PAGO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("transferencia", "Transferencia"),
        ("transbank", "Transbank"),
        ("cheque", "Cheque"),
        ("otro", "Otro")
    ]
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    comprobante = models.ImageField(upload_to="payments/comprobantes/", blank=True, null=True)
    referencia = models.CharField(max_length=100, blank=True, null=True, help_text="Número de transferencia, cheque, etc.")
    notas = models.TextField(blank=True, null=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    # Ventas asociadas a este pago
    ventas = models.ManyToManyField('Sale', related_name='pagos', blank=True)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Pago {self.uid} - {self.cliente.nombre} - ${self.monto}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
    def asociar_ventas(self, ventas_list):
        """Asocia ventas a este pago y actualiza su estado y saldo pendiente"""
        if not ventas_list:
            return
            
        # Asociar las ventas al pago
        self.ventas.add(*ventas_list)
        
        # Monto disponible para aplicar a las ventas
        monto_disponible = self.monto
        
        # Aplicar el pago a cada venta en orden (primero las más antiguas)
        for venta in ventas_list.order_by('created_at'):
            if monto_disponible <= 0:
                break
                
            # Calcular cuánto se puede aplicar a esta venta
            monto_aplicable = min(monto_disponible, venta.saldo_pendiente)
            
            # Actualizar el saldo pendiente de la venta
            venta.saldo_pendiente -= monto_aplicable
            monto_disponible -= monto_aplicable
            
            # Actualizar estado de la venta según el saldo pendiente
            if venta.saldo_pendiente <= 0:
                venta.pagado = True
                venta.estado_pago = 'completo'
            else:
                venta.estado_pago = 'parcial'
            
            # Guardar los cambios en la venta
            venta.save(update_fields=['pagado', 'saldo_pendiente', 'estado_pago', 'updated_at'])
        
        # Actualizar el cliente para refrescar propiedades calculadas
        self.cliente.save(update_fields=['updated_at'])

class Sale(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    codigo_venta = models.CharField(max_length=32, unique=True, editable=False, null=True, blank=True)
    METODO_PAGO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("transferencia", "Transferencia"),
        ("transbank", "Transbank Manual"),
        ("credito", "Credito")
    ]
    lote = models.ForeignKey('inventory.FruitLot', on_delete=models.CASCADE)
    cliente = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    vendedor = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    peso_vendido = models.DecimalField(max_digits=7, decimal_places=2)
    cajas_vendidas = models.PositiveIntegerField(default=0)
    precio_kg = models.DecimalField(max_digits=7, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    comprobante = models.ImageField(upload_to="sales/comprobantes/", blank=True, null=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    # Campos para manejo de crédito
    pagado = models.BooleanField(default=True, help_text="Indica si la venta a crédito ha sido pagada completamente")
    fecha_vencimiento = models.DateField(null=True, blank=True, help_text="Fecha de vencimiento para pago a crédito")
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Saldo pendiente por pagar de esta venta")
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("parcial", "Pago Parcial"),
        ("completo", "Pago Completo"),
        ("cerrada", "Cerrada")
    ]
    estado_pago = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente", help_text="Estado del pago de la venta")

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        # Generar código de venta si no existe
        if not self.codigo_venta:
            today = datetime.now().strftime('%Y%m%d')
            # Contar ventas del día actual
            prefix = f'VEN-{today}-'
            last_sale = Sale.objects.filter(codigo_venta__startswith=prefix).order_by('-codigo_venta').first()
            if last_sale and last_sale.codigo_venta:
                try:
                    last_number = int(last_sale.codigo_venta.split('-')[-1])
                except Exception:
                    last_number = 0
            else:
                last_number = 0
            self.codigo_venta = f'{prefix}{last_number + 1:05d}'
        
        # Si es una venta a crédito, configurar campos relacionados
        if self.metodo_pago == 'credito':
            # Solo en creación
            if self.pk is None:
                self.pagado = False
                self.estado_pago = 'pendiente'
                self.saldo_pendiente = self.total
                
                # Si no hay fecha de vencimiento, establecer por defecto a 30 días
                if not self.fecha_vencimiento:
                    from datetime import date, timedelta
                    self.fecha_vencimiento = date.today() + timedelta(days=30)
        else:
            # Si no es a crédito, siempre está pagado y sin saldo pendiente
            self.pagado = True
            self.saldo_pendiente = Decimal('0.00')
            self.estado_pago = 'completo'
        
        # Guardar la venta
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta {self.codigo_venta or self.id} - Lote {self.lote_id} - Cliente: {self.cliente.nombre if self.cliente else 'Ocasional'}"

class SalePending(BaseModel):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("cancelada", "Cancelada"),
        ("expirada", "Expirada"),
    ]
    lote = models.ForeignKey('inventory.FruitLot', on_delete=models.CASCADE)
    cliente = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad_kg = models.DecimalField(max_digits=7, decimal_places=2)
    cantidad_cajas = models.PositiveIntegerField(default=0)
    # Datos básicos del cliente ocasional
    nombre_cliente = models.CharField(max_length=100, blank=True, null=True)
    rut_cliente = models.CharField(max_length=20, blank=True, null=True)
    telefono_cliente = models.CharField(max_length=20, blank=True, null=True)
    email_cliente = models.EmailField(blank=True, null=True)
    vendedor = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, blank=True, null=True)
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default="pendiente")
    comentarios = models.TextField(blank=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)

    history = HistoricalRecords()

    def __str__(self):
        cliente_str = self.cliente.nombre if self.cliente else (self.nombre_cliente or '')
        return f"Pre-reserva {self.id} - Lote {self.lote_id} - {self.cantidad_kg}kg/{self.cantidad_cajas}cajas - {self.estado} ({cliente_str})"
