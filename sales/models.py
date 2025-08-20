from django.db import models
import uuid
from datetime import datetime
from decimal import Decimal
from core.models import BaseModel
from simple_history.models import HistoricalRecords
from django.utils.translation import gettext_lazy as _
# No importar modelos de otras apps arriba para evitar ciclos

# Importar modelos de facturación
from .models_billing import BillingInfo

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
        # Suma de los saldos pendientes de todas las ventas a crédito no pagadas
        # Esto tiene en cuenta los pagos parciales realizados
        ventas_credito = self.sales.filter(metodo_pago='credito', pagado=False).aggregate(
            total=models.Sum('saldo_pendiente')
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
    # Eliminamos la referencia directa al lote para permitir múltiples productos
    cliente = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    vendedor = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    # Ya no necesitamos campos específicos para cada tipo de producto a nivel de venta
    # porque ahora cada item de venta tendrá sus propios campos
    
    # Común para ambos tipos
    cajas_vendidas = models.PositiveIntegerField(default=0)
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
    
    # Campos para cancelación/anulación (soft delete)
    cancelada = models.BooleanField(default=False)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True, null=True)
    cancelada_por = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_canceladas')
    autorizada_por = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_autorizadas')
    
    # Campos para concesión
    es_concesion = models.BooleanField(default=False, help_text="Indica si esta venta incluye productos en concesión")
    comision_ganada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                        help_text="Comisión total ganada por la venta de productos en concesión")
    proveedor_original = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, 
                                         related_name='ventas_concesion',
                                         null=True, blank=True,
                                         help_text="Proveedor propietario original del producto en concesión")

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

    def cancelar_venta(self, usuario_cancela, usuario_autoriza=None, motivo=""):
        """
        Cancela la venta de manera segura con auditoría completa.
        No elimina la venta, solo la marca como cancelada.
        """
        from django.utils import timezone
        
        if self.cancelada:
            raise ValueError("Esta venta ya ha sido cancelada")
        
        # Marcar como cancelada con auditoría
        self.cancelada = True
        self.fecha_cancelacion = timezone.now()
        self.motivo_cancelacion = motivo
        self.cancelada_por = usuario_cancela
        self.autorizada_por = usuario_autoriza or usuario_cancela
        
        # Guardar los cambios
        self.save()
        
        # TODO: Aquí se podría añadir lógica para revertir el impacto en inventario
        # y generar notificaciones o registros adicionales
        
        return True
    
    def puede_cancelarse(self):
        """
        Verifica si la venta puede ser cancelada.
        """
        if self.cancelada:
            return False, "La venta ya está cancelada"
        
        # Aquí se pueden añadir más validaciones de negocio
        # Por ejemplo: tiempo límite, permisos especiales, etc.
        
        return True, "La venta puede ser cancelada"
    
    @property
    def estado_display(self):
        """
        Devuelve el estado de la venta considerando si está cancelada.
        """
        if self.cancelada:
            return "Cancelada"
        return self.get_estado_pago_display()

    def __str__(self):
        cliente_str = self.cliente.nombre if self.cliente else 'Ocasional'
        estado_str = " [CANCELADA]" if self.cancelada else ""
        
        # Nuevo formato para el modelo con múltiples ítems
        items_count = self.items.count()
        total_str = f"${self.total}" if self.total else ""
        
        return f"Venta {self.codigo_venta or self.id} - {items_count} productos - {total_str} - Cliente: {cliente_str}{estado_str}"

class SaleItem(BaseModel):
    """Modelo para representar los ítems individuales de una venta"""
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    venta = models.ForeignKey('Sale', on_delete=models.CASCADE, related_name='items')
    lote = models.ForeignKey('inventory.FruitLot', on_delete=models.PROTECT)
    
    # Campos para productos tipo palta (por peso)
    peso_vendido = models.DecimalField(max_digits=7, decimal_places=2, default=0, 
                                     help_text="Peso vendido en kg (para productos tipo palta)")
    precio_kg = models.DecimalField(max_digits=7, decimal_places=2, default=0, 
                                  help_text="Precio por kg (para productos tipo palta)")
    
    # Campos para productos tipo otro (por unidades)
    unidades_vendidas = models.PositiveIntegerField(default=0, 
                                                 help_text="Cantidad de unidades vendidas (para productos que no son palta)")
    precio_unidad = models.DecimalField(max_digits=7, decimal_places=2, default=0, 
                                      help_text="Precio por unidad (para productos que no son palta)")
    
    # Campos comunes
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, 
                                 help_text="Subtotal del ítem (precio * cantidad)")
    
    # Campos para concesión
    es_concesion = models.BooleanField(default=False, 
                                     help_text="Indica si este ítem es de un producto en concesión")
    comision_ganada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                        help_text="Comisión ganada por la venta de este ítem en concesión")
    proveedor_original = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT, 
                                         related_name='items_vendidos_concesion',
                                         null=True, blank=True,
                                         help_text="Proveedor propietario original del producto en concesión")
    
    def save(self, *args, **kwargs):
        # Verificar si es un objeto nuevo (sin ID aún)
        is_new = self.pk is None
        
        # Guardar el objeto
        super().save(*args, **kwargs)
        
        # Si es un objeto nuevo, actualizar el inventario
        if is_new and not self.venta.cancelada:
            # Actualizar el inventario del lote
            if self.lote:
                # Para productos tipo palta, actualizar por peso
                if self.lote.producto and self.lote.producto.tipo_producto == 'palta':
                    # Actualizar peso neto
                    if self.peso_vendido > 0:
                        self.lote.peso_neto = max(0, self.lote.peso_neto - self.peso_vendido)
                        
                # Para todos los productos, actualizar cajas
                if self.unidades_vendidas > 0:
                    self.lote.cantidad_cajas = max(0, self.lote.cantidad_cajas - self.unidades_vendidas)
                    
                # Guardar los cambios en el lote
                self.lote.save(update_fields=['peso_neto', 'cantidad_cajas', 'updated_at'])
    
    def __str__(self):
        if self.lote and self.lote.producto:
            if self.lote.producto.tipo_producto == 'palta':
                return f"Ítem {self.id} - {self.lote.producto.nombre} - {self.peso_vendido}kg"
            else:
                return f"Ítem {self.id} - {self.lote.producto.nombre} - {self.unidades_vendidas}unidades"
        return f"Ítem {self.id}"
    
    class Meta:
        verbose_name = _("Sale Item")
        verbose_name_plural = _("Sale Items")


class SalePending(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    codigo_venta = models.CharField(max_length=32, unique=True, editable=False, null=True, blank=True)
    
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("cancelada", "Cancelada"),
        ("expirada", "Expirada"),
    ]
    # Campos básicos de la venta pendiente
    cliente = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Ya no necesitamos campos específicos para cada tipo de producto a nivel de venta pendiente
    # porque ahora cada item de venta pendiente tendrá sus propios campos
    
    # Común para ambos tipos
    cantidad_cajas = models.PositiveIntegerField(default=0)
    
    # Datos básicos del cliente ocasional
    nombre_cliente = models.CharField(max_length=100, blank=True, null=True)
    rut_cliente = models.CharField(max_length=20, blank=True, null=True)
    telefono_cliente = models.CharField(max_length=20, blank=True, null=True)
    email_cliente = models.EmailField(blank=True, null=True)
    
    # Campos adicionales para facilitar la conversión a venta confirmada
    precio_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    metodo_pago = models.CharField(max_length=20, choices=Sale.METODO_PAGO_CHOICES, blank=True, null=True)
    comprobante = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    
    # Campos de control
    vendedor = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, blank=True, null=True)
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default="pendiente")
    comentarios = models.TextField(blank=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if not self.codigo_venta:
            today = datetime.now().strftime('%Y%m%d')
            prefix = f'PRE-{today}-'
            last_pending_sale = SalePending.objects.filter(codigo_venta__startswith=prefix).order_by('-codigo_venta').first()
            
            last_number = 0
            if last_pending_sale and last_pending_sale.codigo_venta:
                try:
                    last_number = int(last_pending_sale.codigo_venta.split('-')[-1])
                except (ValueError, IndexError):
                    last_number = 0 # Fallback en caso de formato inesperado
            
            self.codigo_venta = f'{prefix}{last_number + 1:05d}'
        
        super().save(*args, **kwargs)

    def __str__(self):
        cliente_str = self.cliente.nombre if self.cliente else (self.nombre_cliente or '')
        return f"Pre-reserva {self.id} - {self.estado} ({cliente_str})"


class SalePendingItem(BaseModel):
    """Modelo para representar los ítems individuales de una venta pendiente"""
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    venta_pendiente = models.ForeignKey('SalePending', on_delete=models.CASCADE, related_name='items')
    lote = models.ForeignKey('inventory.FruitLot', on_delete=models.PROTECT)
    
    # Campos para productos tipo palta (por peso)
    cantidad_kg = models.DecimalField(max_digits=7, decimal_places=2, default=0, 
                                   help_text="Cantidad en kg (para productos tipo palta)")
    precio_kg = models.DecimalField(max_digits=7, decimal_places=2, default=0, 
                                  help_text="Precio por kg (para productos tipo palta)")
    
    # Campos para productos tipo otro (por unidades)
    cantidad_unidades = models.PositiveIntegerField(default=0) 
    precio_unidad = models.DecimalField(max_digits=7, decimal_places=2, default=0, 
                                      help_text="Precio por unidad (para productos que no son palta)")
    
    # Campos comunes
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, 
                                 help_text="Subtotal del ítem (precio * cantidad)")
    
    def __str__(self):
        if self.lote and self.lote.producto:
            if self.lote.producto.tipo_producto == 'palta':
                return f"Ítem pendiente {self.id} - {self.lote.producto.nombre} - {self.cantidad_kg}kg"
            else:
                return f"Ítem pendiente {self.id} - {self.lote.producto.nombre} - {self.cantidad_unidades}unidades"
        return f"Ítem pendiente {self.id}"
    
    class Meta:
        verbose_name = _("Sale Pending Item")
        verbose_name_plural = _("Sale Pending Items")
