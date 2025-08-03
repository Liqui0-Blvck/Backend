import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from core.models import BaseModel
from simple_history.models import HistoricalRecords
# No importar modelos de otras apps arriba para evitar ciclos

class Shift(BaseModel):
    """
    Modelo para registrar los turnos de trabajo.
    Permite llevar un control detallado de todos los turnos de trabajo.
    """
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ESTADO_CHOICES = [
        ("abierto", "Abierto"),
        ("cerrado", "Cerrado"),
    ]
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    usuario_abre = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name="shifts_abiertos")
    usuario_cierra = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name="shifts_cerrados", null=True, blank=True)
    fecha_apertura = models.DateTimeField()
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default="abierto")
    motivo_diferencia = models.TextField(blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"Turno {self.uid} - {self.estado}"
    
    @classmethod
    def get_turno_activo(cls, business):
        """Obtiene el turno activo para un negocio específico"""
        return cls.objects.filter(business=business, estado="abierto").first()


class BoxRefill(BaseModel):
    """
    Modelo para registrar el descuento de cajas por concepto de relleno durante un turno.
    Solo se puede realizar esta acción si hay un turno activo.
    """
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="box_refills", to_field='uid')
    fruit_lot = models.ForeignKey('inventory.FruitLot', on_delete=models.CASCADE, related_name="box_refills")
    cantidad_cajas = models.PositiveIntegerField(help_text="Cantidad de cajas descontadas por relleno")
    motivo = models.TextField(help_text="Motivo del descuento de cajas")
    usuario = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    fecha = models.DateTimeField(default=timezone.now)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Relleno de {self.cantidad_cajas} cajas - Lote: {self.fruit_lot.uid if hasattr(self.fruit_lot, 'uid') else self.fruit_lot.id}"
    
    class Meta:
        verbose_name = "Relleno de Cajas"
        verbose_name_plural = "Rellenos de Cajas"
        ordering = ["-fecha"]


class ShiftExpense(BaseModel):
    """
    Modelo para registrar los gastos incurridos durante un turno.
    Permite llevar un control detallado de todos los gastos operativos.
    """
    CATEGORIA_CHOICES = [
        ("transporte", "Transporte"),
        ("insumos", "Insumos"),
        ("servicios", "Servicios"),
        ("personal", "Personal"),
        ("mantenimiento", "Mantenimiento"),
        ("impuestos", "Impuestos"),
        ("otros", "Otros"),
    ]
    
    METODO_PAGO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("transferencia", "Transferencia"),
        ("tarjeta_debito", "Tarjeta de Débito"),
        ("tarjeta_credito", "Tarjeta de Crédito"),
        ("otro", "Otro"),
    ]
    
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="expenses", to_field='uid')
    descripcion = models.CharField(max_length=255, help_text="Descripción del gasto")
    monto = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], help_text="Monto del gasto")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default="otros", help_text="Categoría del gasto")
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, default="efectivo", help_text="Método de pago utilizado")
    comprobante = models.FileField(upload_to='comprobantes_gastos/', null=True, blank=True, help_text="Imagen o PDF del comprobante")
    numero_comprobante = models.CharField(max_length=50, blank=True, help_text="Número de factura o boleta")
    proveedor = models.CharField(max_length=100, blank=True, help_text="Nombre del proveedor o beneficiario")
    autorizado_por = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name="gastos_autorizados", help_text="Usuario que autorizó el gasto")
    registrado_por = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name="gastos_registrados", help_text="Usuario que registró el gasto")
    fecha = models.DateTimeField(default=timezone.now, help_text="Fecha y hora del gasto")
    notas = models.TextField(blank=True, help_text="Notas adicionales sobre el gasto")
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Gasto: {self.descripcion} - ${self.monto}"
    
    class Meta:
        verbose_name = "Gasto de Turno"
        verbose_name_plural = "Gastos de Turno"
        ordering = ["-fecha"]
