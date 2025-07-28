from django.db import models
import uuid
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import BaseModel
from simple_history.models import HistoricalRecords

class Product(BaseModel):
    options = [
        ('caja', 'Caja'),
        ('unidad', 'Unidad'),
        ('kilogramo', 'Kilogramo'),
    ]
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    marca = models.CharField(max_length=50, blank=True)
    unidad = models.CharField(max_length=20, default="caja", choices=options)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    activo = models.BooleanField(default=True)
    image_path = models.ImageField(upload_to='product_images', blank=True, null=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nombre} ({self.marca})"

class PalletType(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    nombre = models.CharField(max_length=64)
    peso_pallet = models.DecimalField(max_digits=7, decimal_places=2)
    descripcion = models.TextField(blank=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.nombre

class BoxType(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    nombre = models.CharField(max_length=64)
    descripcion = models.TextField(blank=True)
    peso_caja = models.DecimalField(max_digits=6, decimal_places=2)
    peso_pallet = models.DecimalField(max_digits=7, decimal_places=2)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

class FruitLot(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    producto = models.ForeignKey('Product', on_delete=models.CASCADE, null=True, blank=True)
    marca = models.CharField(max_length=50, blank=True)
    proveedor = models.CharField(max_length=64)
    procedencia = models.CharField(max_length=64)
    pais = models.CharField(max_length=32)
    calibre = models.CharField(max_length=16)
    box_type = models.ForeignKey('BoxType', on_delete=models.CASCADE)
    pallet_type = models.ForeignKey('PalletType', on_delete=models.CASCADE, null=True, blank=True)
    cantidad_cajas = models.PositiveIntegerField()
    peso_bruto = models.DecimalField(max_digits=8, decimal_places=2)
    peso_neto = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    qr_code = models.CharField(max_length=128, unique=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    fecha_ingreso = models.DateField(default=timezone.now)
    estado_maduracion = models.CharField(max_length=16, choices=[('verde','Verde'),('pre-maduro','Pre-maduro'),('maduro','Maduro'),('sobremaduro','Sobremaduro')], default='verde')
    fecha_maduracion = models.DateField(null=True, blank=True)
    porcentaje_perdida_estimado = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    costo_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    costo_diario_almacenaje = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Campos para rango de precios sugeridos
    precio_sugerido_min = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Precio mínimo sugerido por kg")
    precio_sugerido_max = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Precio máximo sugerido por kg")
    # costo_actualizado se calcula sobre la marcha

    estado_lote = models.CharField(
        max_length=20, 
        choices=[
            ('activo', 'Con cajas disponibles'),
            ('agotado', 'Sin cajas disponibles'),
            ('cajas_recuperadas', 'Cajas vacías recuperadas')
        ],
        default='activo'
    )

    history = HistoricalRecords()

    def costo_actualizado(self):
        from datetime import date
        dias = (date.today() - self.fecha_ingreso).days
        return self.costo_inicial + (self.costo_diario_almacenaje * dias)
        
    def peso_disponible(self):
        """Calcula el peso disponible del lote (peso neto - peso reservado)"""
        from django.db.models import Sum
        # Evitar importación circular usando el modelo directamente
        neto = float(self.peso_neto or 0)
        # Usamos el modelo desde el mismo app sin importarlo
        reservado = self.__class__._meta.apps.get_model('inventory', 'StockReservation').objects.filter(lote=self).aggregate(total=Sum('cantidad_kg'))['total'] or 0
        return neto - float(reservado) if neto > float(reservado) else 0

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        # Validaciones para evitar inconsistencias
        if self.cantidad_cajas < 0:
            raise ValidationError('No puedes tener cajas negativas en el lote.')
        if self.peso_neto is not None and self.peso_neto < 0:
            raise ValidationError('No puedes tener peso neto negativo en el lote.')
        # Si el peso_neto no está definido, lo calcula
        if self.peso_neto is None:
            self.peso_neto = self.peso_bruto - (self.box_type.peso_caja * self.cantidad_cajas + (self.pallet_type.peso_pallet if self.pallet_type else 0))
        if not self.qr_code:
            import uuid
            self.qr_code = f"LOT-{uuid.uuid4()}"
        # Actualiza estado_lote automáticamente
        if self.cantidad_cajas == 0:
            self.estado_lote = 'agotado'
        elif self.cantidad_cajas > 0 and self.estado_lote == 'agotado':
            self.estado_lote = 'activo'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.nombre} - Lote {self.id} ({self.estado_maduracion})"

class MadurationHistory(models.Model):
    lote = models.ForeignKey(FruitLot, on_delete=models.CASCADE, related_name='maduration_history')
    estado_maduracion = models.CharField(max_length=16, choices=[('verde','Verde'),('pre-maduro','Pre-maduro'),('maduro','Maduro'),('sobremaduro','Sobremaduro')])
    fecha_cambio = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.lote} - {self.estado_maduracion} ({self.fecha_cambio})"

class StockReservation(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    ESTADO_CHOICES = [
        ("en_proceso", "En proceso"),
        ("confirmada", "Confirmada"),
        ("cancelada", "Cancelada"),
        ("expirada", "Expirada"),
    ]
    lote = models.ForeignKey('FruitLot', on_delete=models.CASCADE, related_name='reservas')
    usuario = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    cantidad_kg = models.DecimalField(max_digits=7, decimal_places=2)
    cantidad_cajas = models.PositiveIntegerField(default=0)
    # Cliente frecuente (opcional)
    cliente = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    # Datos básicos del cliente ocasional
    nombre_cliente = models.CharField(max_length=100, blank=True, null=True)
    rut_cliente = models.CharField(max_length=20, blank=True, null=True)
    telefono_cliente = models.CharField(max_length=20, blank=True, null=True)
    email_cliente = models.EmailField(blank=True, null=True)
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default="en_proceso")
    timeout_minutos = models.PositiveIntegerField(default=2)  # configurable

    history = HistoricalRecords()

    def is_expired(self):
        return self.estado == "en_proceso" and (timezone.now() - self.created_at).total_seconds() > self.timeout_minutos * 60

    def __str__(self):
        cliente_str = self.cliente.nombre if self.cliente else (self.nombre_cliente or '')
        return f"Reserva {self.id} - Lote {self.lote_id} - {self.cantidad_kg}kg/{self.cantidad_cajas}cajas - {self.estado} ({cliente_str})"

class Supplier(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    """
    Modelo para gestionar los proveedores de fruta.
    """
    nombre = models.CharField(max_length=100)
    rut = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    activo = models.BooleanField(default=True)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.nombre} ({self.rut})"
    
    class Meta:
        verbose_name = _("Supplier")
        verbose_name_plural = _("Suppliers")

class GoodsReception(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    """
    Modelo principal para registrar la recepción de mercadería (fruta) en bodega.
    Funciona como una guía de entrada que documenta la llegada de productos.
    """
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de revisión"),
        ("revisado", "Revisado"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado parcial/total"),
    ]
    
    # Información general
    numero_guia = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Número de guía interna")
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    proveedor = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='recepciones')
    numero_guia_proveedor = models.CharField(max_length=50, blank=True, null=True, 
                                           help_text="Número de guía o factura del proveedor")

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.numero_guia:
            year = timezone.now().year
            prefix = f'GE-{year}-'
            
            # Buscar el último número de guía con este prefijo
            last = GoodsReception.objects.filter(numero_guia__startswith=prefix).order_by('-numero_guia').first()
            
            if last and last.numero_guia:
                try:
                    # Extraer el número y convertirlo a entero
                    last_number = int(last.numero_guia.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
                
            # Generar el nuevo número de guía
            new_guide_number = f'{prefix}{next_number:04d}'
            
            # Verificar que no exista ya este número (por seguridad adicional)
            while GoodsReception.objects.filter(numero_guia=new_guide_number).exists():
                next_number += 1
                new_guide_number = f'{prefix}{next_number:04d}'
                
            self.numero_guia = new_guide_number
            
        super().save(*args, **kwargs)
    
    # Responsables
    recibido_por = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT, 
                                    related_name='recepciones_recibidas')
    revisado_por = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT, 
                                    related_name='recepciones_revisadas', 
                                    blank=True, null=True)
    
    # Estado y observaciones
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    observaciones = models.TextField(blank=True, null=True)
    
    # Monto total de la recepción (para cálculos y reportes)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, 
                                    help_text="Monto total de la recepción")
    
    # Totales (se calculan automáticamente a partir de los detalles)
    total_pallets = models.PositiveIntegerField(default=0)
    total_cajas = models.PositiveIntegerField(default=0)
    total_peso_bruto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Relación con negocio
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Recepción #{self.numero_guia} - {self.proveedor.nombre} ({self.fecha_recepcion.strftime('%d/%m/%Y')})"
    
    def actualizar_totales(self):
        """
        Actualiza los totales basados en los detalles de la recepción y
        calcula el monto_total basado en los lotes vinculados (peso_neto * costo_inicial)
        """
        detalles = self.detalles.all()
        self.total_pallets = detalles.count()
        self.total_cajas = sum(d.cantidad_cajas for d in detalles)
        self.total_peso_bruto = sum(d.peso_bruto for d in detalles)
        
        # Calcular el monto total basado en los lotes vinculados
        monto_total = 0
        for detalle in detalles:
            if detalle.lote_creado:
                # Si hay un lote vinculado, usar su peso_neto y costo_inicial
                lote = detalle.lote_creado
                monto_total += float(lote.peso_neto) * float(lote.costo_inicial)
            else:
                # Si no hay lote vinculado, usar el peso_neto del detalle y su costo
                monto_total += float(detalle.peso_neto) * float(detalle.costo)
        
        self.monto_total = monto_total
        self.save()
    
    class Meta:
        verbose_name = _("Goods Reception")
        verbose_name_plural = _("Goods Receptions")
        ordering = ['-fecha_recepcion']

class ReceptionDetail(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    """
    Detalle de cada pallet/lote recibido en una recepción de mercadería.
    """
    CALIDAD_CHOICES = [
        (5, "Excelente"),
        (4, "Buena"),
        (3, "Regular"),
        (2, "Deficiente"),
        (1, "Mala"),
    ]
    
    # Relación con la recepción principal
    recepcion = models.ForeignKey(GoodsReception, on_delete=models.CASCADE, related_name='detalles')
    
    # Información del producto
    producto = models.ForeignKey('Product', on_delete=models.PROTECT)
    variedad = models.CharField(max_length=50, blank=True, null=True)
    calibre = models.CharField(max_length=20, blank=True, null=True)
    box_type = models.ForeignKey('BoxType', on_delete=models.PROTECT, blank=True, null=True)
    
    # Cantidades
    numero_pallet = models.CharField(max_length=20, help_text="Identificador único del pallet/lote")
    cantidad_cajas = models.PositiveIntegerField()
    peso_bruto = models.DecimalField(max_digits=8, decimal_places=2, help_text="Peso bruto en kg")
    peso_tara = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Peso de embalaje/tara en kg")
    
    # Calidad y estado
    calidad = models.PositiveSmallIntegerField(choices=CALIDAD_CHOICES, default=3)
    temperatura = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, 
                                    help_text="Temperatura en °C al momento de recepción")
    estado_maduracion = models.CharField(max_length=50, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    
    # Información económica
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                             help_text="Costo por caja o unidad")
    porcentaje_perdida_estimado = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                                   help_text="Porcentaje estimado de pérdida para este lote")
    
    # Campos para trazabilidad
    lote_creado = models.ForeignKey('FruitLot', on_delete=models.SET_NULL, 
                                   blank=True, null=True, related_name='detalle_recepcion')
    
    history = HistoricalRecords()
    
    @property
    def peso_neto(self):
        """Calcula el peso neto restando la tara del peso bruto"""
        return self.peso_bruto - self.peso_tara
    
    def __str__(self):
        return f"Pallet {self.numero_pallet} - {self.producto.nombre} ({self.cantidad_cajas} cajas, {self.peso_bruto}kg)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar totales en la recepción principal
        self.recepcion.actualizar_totales()
    
    class Meta:
        verbose_name = _("Reception Detail")
        verbose_name_plural = _("Reception Details")
        unique_together = ('recepcion', 'numero_pallet')

class ReceptionImage(BaseModel):
    """
    Imágenes asociadas a una recepción de mercadería o a un detalle específico.
    """
    recepcion = models.ForeignKey(GoodsReception, on_delete=models.CASCADE, related_name='imagenes')
    detalle = models.ForeignKey(ReceptionDetail, on_delete=models.CASCADE, 
                               related_name='imagenes', blank=True, null=True)
    imagen = models.ImageField(upload_to='recepciones/')
    descripcion = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        base = f"Imagen {self.id} - {self.recepcion.numero_guia}"
        if self.detalle:
            return f"{base} - Pallet {self.detalle.numero_pallet}"
        return base
    
    class Meta:
        verbose_name = _("Reception Image")
        verbose_name_plural = _("Reception Images")

# Señales para integración automática con inventario
@receiver(post_save, sender=GoodsReception)
def crear_lotes_al_aprobar_recepcion(sender, instance, created, **kwargs):
    """
    Cuando una recepción cambia a estado 'aprobado', crea automáticamente
    lotes de fruta (FruitLot) para cada detalle de la recepción que no tenga
    un lote asociado aún.
    """
    # Solo proceder si la recepción está en estado aprobado
    if instance.estado == "aprobado":
        # Procesar solo detalles que no tienen lote creado aún
        detalles_sin_lote = instance.detalles.filter(lote_creado__isnull=True)
        
        # Usar una bandera para evitar recursividad y duplicación
        if not hasattr(instance, '_lotes_creados') or not instance._lotes_creados:
            # Marcar que ya se procesaron los lotes para esta instancia
            instance._lotes_creados = True
            
            for detalle in detalles_sin_lote:
                # Crear un nuevo lote de fruta basado en el detalle de recepción
                lote = FruitLot(
                    producto=detalle.producto,
                    marca=detalle.variedad or "",  # Usar variedad como marca si está disponible
                    proveedor=instance.proveedor.nombre,
                    procedencia=instance.proveedor.direccion or "No especificada",
                    pais="Chile",  # Valor por defecto, podría ser un campo en Proveedor
                    calibre=detalle.calibre or "No especificado",
                    box_type=detalle.box_type,
                    cantidad_cajas=detalle.cantidad_cajas,
                    peso_bruto=detalle.peso_bruto,
                    peso_neto=detalle.peso_neto,
                    business=instance.business,
                    fecha_ingreso=instance.fecha_recepcion.date(),
                    estado_maduracion=detalle.estado_maduracion or "verde",
                    costo_inicial=detalle.costo,  # Usar el costo del detalle de recepción
                    porcentaje_perdida_estimado=detalle.porcentaje_perdida_estimado,  # Usar el porcentaje de pérdida estimado del detalle
                )
                
                # Guardar el lote
                lote.save()
                
                # Registrar el cambio de estado de maduración inicial
                MadurationHistory.objects.create(
                    lote=lote,
                    estado_maduracion=lote.estado_maduracion
                )
                
                # Actualizar el detalle con referencia al lote creado
                # Usar update para evitar que se dispare la señal post_save de ReceptionDetail
                ReceptionDetail.objects.filter(pk=detalle.pk).update(lote_creado=lote)
                
                # Log para debugging
                print(f"Lote creado automáticamente: {lote} desde recepción {instance.numero_guia}")

@receiver(post_save, sender=ReceptionDetail)
def actualizar_lote_desde_detalle(sender, instance, created, **kwargs):
    """
    Si un detalle de recepción ya tiene un lote asociado y la recepción está aprobada,
    actualiza el lote con la información más reciente del detalle.
    """
    # Evitar actualizaciones recursivas o innecesarias
    if hasattr(instance, '_actualizando_lote') and instance._actualizando_lote:
        return
    
    # Solo actualizar si hay un lote asociado y la recepción está aprobada
    # Y NO estamos en el proceso de crear lotes desde la recepción
    if instance.lote_creado and instance.recepcion.estado == "aprobado" and not hasattr(instance.recepcion, '_lotes_creados'):
        instance._actualizando_lote = True
        lote = instance.lote_creado
        
        # Actualizar campos relevantes
        lote.cantidad_cajas = instance.cantidad_cajas
        lote.peso_bruto = instance.peso_bruto
        lote.peso_neto = instance.peso_neto
        
        # Si el estado de maduración cambió, actualizar y registrar
        if instance.estado_maduracion and lote.estado_maduracion != instance.estado_maduracion:
            estado_anterior = lote.estado_maduracion
            lote.estado_maduracion = instance.estado_maduracion
            
            # Registrar el cambio en el historial
            MadurationHistory.objects.create(
                lote=lote,
                estado_maduracion=lote.estado_maduracion
            )
        
        # Guardar los cambios
        lote.save()
        
        # Eliminar la bandera
        instance._actualizando_lote = False


class SupplierPayment(BaseModel):
    """
    Modelo para registrar pagos individuales a proveedores
    """
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    recepcion = models.ForeignKey('GoodsReception', on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=12, decimal_places=2, help_text='Monto del pago realizado')
    fecha_pago = models.DateTimeField(default=timezone.now, help_text='Fecha y hora en que se realizó el pago')
    metodo_pago = models.CharField(
        max_length=20,
        choices=[
            ('efectivo', 'Efectivo'),
            ('transferencia', 'Transferencia'),
            ('cheque', 'Cheque'),
            ('otro', 'Otro')
        ],
        default='efectivo',
        help_text='Método utilizado para realizar el pago'
    )
    comprobante = models.FileField(upload_to='comprobantes_pago', null=True, blank=True, 
                                 help_text='Archivo de comprobante de pago (opcional)')
    notas = models.TextField(blank=True, null=True, help_text='Notas adicionales sobre el pago')
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    history = HistoricalRecords()
    
    def save(self, *args, **kwargs):
        # Guardar el pago sin actualizar campos en GoodsReception
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Pago {self.id} - {self.recepcion.numero_guia} - ${self.monto:,.0f}"
    
    class Meta:
        verbose_name = _("Supplier Payment")
        verbose_name_plural = _("Supplier Payments")
        ordering = ['-fecha_pago']
