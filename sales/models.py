from django.db import models
import uuid
from datetime import datetime
from core.models import BaseModel
from simple_history.models import HistoricalRecords
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

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nombre} ({self.rut}){' [Frecuente]' if self.frecuente else ''}"

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
    cliente = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True)
    vendedor = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    peso_vendido = models.DecimalField(max_digits=7, decimal_places=2)
    cajas_vendidas = models.PositiveIntegerField(default=0)
    precio_kg = models.DecimalField(max_digits=7, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    comprobante = models.ImageField(upload_to="sales/comprobantes/", blank=True, null=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
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
