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
    TIPO_PRODUCTO_CHOICES = [
        ('palta', 'Palta'),
        ('otro', 'Otro'),
    ]
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    marca = models.CharField(max_length=50, blank=True)
    unidad = models.CharField(max_length=20, default="caja", choices=options)
    tipo_producto = models.CharField(max_length=10, choices=TIPO_PRODUCTO_CHOICES, default='palta', help_text='Tipo de producto: palta o otro')
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    activo = models.BooleanField(default=True)
    image_path = models.ImageField(upload_to='product_images', blank=True, null=True)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        """Asegura que el tipo de producto se asigne automáticamente."""
        if 'palta' in self.nombre.lower():
            self.tipo_producto = 'palta'
        else:
            self.tipo_producto = 'otro'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.marca})"

class PalletType(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    nombre = models.CharField(max_length=64)
    peso_pallet = models.DecimalField(max_digits=7, decimal_places=2)  # Mantener nombre para compatibilidad
    descripcion = models.TextField(blank=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.nombre

class BoxType(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    BOX_NAME_CHOICES = [
        ('madera', 'Madera'),
        ('toro', 'Toro'),
        ('plastico', 'Plástico'),
        ('rejilla', 'Rejilla'),
    ]
    nombre = models.CharField(max_length=64, choices=BOX_NAME_CHOICES, default='rejilla')
    descripcion = models.TextField(blank=True)
    peso_caja = models.DecimalField(max_digits=6, decimal_places=2)
    capacidad_por_caja = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    # Máxima cantidad de cajas que se recomienda o permite por pallet para este tipo de caja
    cantidad_max_cajas = models.PositiveIntegerField(null=True, blank=True, help_text="Límite recomendado de cajas por pallet para este tipo de caja")
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    # Control de inventario de cajas vacías disponibles en bodega
    stock_cajas_vacias = models.PositiveIntegerField(default=0, help_text="Cantidad de cajas vacías disponibles en bodega para este tipo de caja")

    def __str__(self):
        return self.nombre

class FruitLot(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    producto = models.ForeignKey('Product', on_delete=models.CASCADE, null=True, blank=True)
    marca = models.CharField(max_length=50, blank=True)
    # Calibraje/calidad (5ta a Super Extra)
    CALIDAD_CALIBRAJE_CHOICES = [
        ('DESCARTE', 'Descarte'),
        ('5TA', '5ta'),
        ('4TA', '4ta'),
        ('3RA', '3ra'),
        ('2DA', '2da'),
        ('1RA', '1ra'),
        ('EXTRA', 'Extra'),
        ('SUPER_EXTRA', 'Super Extra'),
    ]
    calidad = models.CharField(max_length=16, choices=CALIDAD_CALIBRAJE_CHOICES, default='3RA', help_text="Calibraje/calidad del lote")
    variedad = models.CharField(max_length=50, blank=True, null=True)
    proveedor = models.ForeignKey('Supplier', on_delete=models.CASCADE, null=True, blank=True)
    procedencia = models.CharField(max_length=64)
    pais = models.CharField(max_length=32)
    
    # Campos para concesión
    en_concesion = models.BooleanField(default=False, help_text="Indica si el lote está en concesión")
    comision_por_kilo = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                          help_text="Comisión por kilo vendido (para lotes en concesión)")
    fecha_limite_concesion = models.DateField(null=True, blank=True,
                                            help_text="Fecha límite para vender el lote en concesión")
    propietario_original = models.ForeignKey('Supplier', on_delete=models.PROTECT, 
                                           related_name='lotes_en_concesion',
                                           null=True, blank=True,
                                           help_text="Proveedor propietario original del lote en concesión")
    calibre = models.CharField(max_length=16)
    box_type = models.ForeignKey('BoxType', on_delete=models.CASCADE)
    pallet_type = models.ForeignKey('PalletType', on_delete=models.CASCADE, null=True, blank=True)
    cantidad_cajas = models.PositiveIntegerField()
    # Campos para productos tipo 'otro' (por unidades)
    cantidad_unidades = models.PositiveIntegerField(default=0, help_text="Cantidad total de unidades en el lote (para productos que no son palta)")
    unidades_por_caja = models.PositiveIntegerField(default=0, help_text="Cantidad de unidades por caja (para productos que no son palta)")
    unidades_reservadas = models.PositiveIntegerField(default=0, help_text="Cantidad de unidades reservadas (para productos que no son palta)")
    # Campos para productos tipo 'palta' (por peso)
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
    precio_sugerido_min = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Precio mínimo sugerido por kg o unidad")
    precio_sugerido_max = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Precio máximo sugerido por kg o unidad")
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
        # Solo aplica para productos tipo palta
        if not self.producto or self.producto.tipo_producto != 'palta':
            return 0
            
        from django.db.models import Sum
        # Evitar importación circular usando el modelo directamente
        neto = float(self.peso_neto or 0)
        # Usamos el modelo desde el mismo app sin importarlo
        reservado = self.__class__._meta.apps.get_model('inventory', 'StockReservation').objects.filter(lote=self, estado='en_proceso').aggregate(total=Sum('kg_reservados'))['total'] or 0
        return neto - float(reservado) if neto > float(reservado) else 0
        
    def unidades_disponibles(self):
        """Calcula las unidades disponibles del lote (cantidad_unidades - unidades_reservadas)"""
        # Solo aplica para productos tipo otro (no palta)
        if not self.producto or self.producto.tipo_producto != 'otro':
            return 0
            
        return max(0, self.cantidad_cajas - self.unidades_reservadas)

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        # Validaciones para evitar inconsistencias
        if self.cantidad_cajas < 0:
            raise ValidationError('No puedes tener cajas negativas en el lote.')
            
        # Validaciones específicas según el tipo de producto
        if self.producto:
            if self.producto.tipo_producto == 'palta':
                # Validaciones para productos tipo palta (por peso)
                if self.peso_neto is not None and self.peso_neto < 0:
                    raise ValidationError('No puedes tener peso neto negativo en el lote.')
                # Si el peso_neto no está definido, lo calcula
                if self.peso_neto is None:
                    self.peso_neto = self.peso_bruto - (self.box_type.peso_caja * self.cantidad_cajas + (self.pallet_type.peso_pallet if self.pallet_type else 0))
            elif self.producto.tipo_producto == 'otro':
                # Validaciones para productos tipo otro (por unidades)
                if self.cantidad_unidades < 0:
                    raise ValidationError('No puedes tener unidades negativas en el lote.')

                # Actualizar cantidad_unidades basado en cajas si es necesario
                if self.unidades_por_caja > 0 and self.cantidad_unidades == 0:
                    self.cantidad_unidades = self.cantidad_cajas * self.unidades_por_caja
        
        if not self.qr_code:
            import uuid
            self.qr_code = f"LOT-{uuid.uuid4()}"
            
        # Actualiza estado_lote automáticamente
        if self.cantidad_cajas == 0:
            self.estado_lote = 'agotado'
        if self.estado_lote != 'agotado':
            es_palta = self.producto and self.producto.tipo_producto == 'palta'
            if es_palta:
                if self.peso_neto <= 0:
                    # self.estado_lote = 'agotado'
                    pass
            else:
                if self.cantidad_cajas <= 0:
                    # self.estado_lote = 'agotado'
                    pass
        
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
    item_venta_pendiente = models.OneToOneField('sales.SalePendingItem', on_delete=models.CASCADE, related_name='reserva', null=True, blank=True)
    usuario = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    cajas_reservadas = models.PositiveIntegerField(default=0, help_text="Cantidad de cajas reservadas para la venta.")
    kg_reservados = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Cantidad de kilogramos reservados (para paltas).")
    unidades_reservadas = models.PositiveIntegerField(default=0, help_text="Cantidad de unidades reservadas (para otros productos).")
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
        if self.lote.producto and self.lote.producto.tipo_producto == 'palta':
            return f"Reserva {self.id} - Lote {self.lote_id} - {self.kg_reservados}kg/{self.cajas_reservadas}cajas - {self.estado} ({cliente_str})"
        else:
            return f"Reserva {self.id} - Lote {self.lote_id} - {self.unidades_reservadas}unidades/{self.cajas_reservadas}cajas - {self.estado} ({cliente_str})"

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
    # Campos para concesión
    en_concesion = models.BooleanField(default=False, 
                                      help_text="Indica si la mercancía está en concesión")
    comision_por_kilo = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                          help_text="Comisión por kilo vendido (para mercancía en concesión)")
    comision_base = models.CharField(max_length=16, null=True, blank=True,
                                     help_text="Base de comisión: kg|caja|unidad|venta")
    comision_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="Monto de comisión según la base seleccionada")
    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                              help_text="Porcentaje de comisión (0-100)")
    fecha_limite_concesion = models.DateField(null=True, blank=True,
                                            help_text="Fecha límite para vender la mercancía en concesión")
    
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de revisión"),
        ("revisado", "Revisado"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado parcial/total"),
    ]
    
    estado_pago = models.CharField(max_length=16, choices=[('pendiente', 'Pendiente'), ('pagado', 'Pagado')], default='pendiente')
    
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
                # Si hay un lote vinculado, usar su peso_neto y costo_inicial (para palta),
                # o cantidad_cajas * costo_inicial (para otros productos)
                lote = detalle.lote_creado
                if getattr(lote.producto, 'tipo_producto', None) == 'palta':
                    monto_total += float(lote.peso_neto or 0) * float(lote.costo_inicial or 0)
                else:
                    monto_total += float(lote.cantidad_cajas or 0) * float(lote.costo_inicial or 0)
            else:
                # Si no hay lote vinculado: estimar según tipo de producto del detalle
                tipo = getattr(detalle.producto, 'tipo_producto', None) if getattr(detalle, 'producto', None) else None
                if tipo == 'palta':
                    peso_neto_estimado = float(detalle.peso_bruto or 0) - float(detalle.peso_tara or 0)
                    monto_total += max(peso_neto_estimado, 0) * float(detalle.costo or 0)
                else:
                    monto_total += float(detalle.cantidad_cajas or 0) * float(detalle.costo or 0)
        
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
    marca = models.CharField(max_length=50, blank=True, null=True)
    variedad = models.CharField(max_length=50, blank=True, null=True)
    calibre = models.CharField(max_length=20, blank=True, null=True)
    box_type = models.ForeignKey('BoxType', on_delete=models.PROTECT, blank=True, null=True)
    
    # Cantidades
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
    
    # Campos para concesión
    en_concesion = models.BooleanField(default=False, help_text="Indica si este lote está en concesión")
    comision_por_kilo = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                         help_text="Comisión por kilo para lotes en concesión")
    fecha_limite_concesion = models.DateField(blank=True, null=True, 
                                           help_text="Fecha límite para vender el producto en concesión")
    
    # Campos para trazabilidad
    lote_creado = models.ForeignKey('FruitLot', on_delete=models.SET_NULL, 
                                   blank=True, null=True, related_name='detalle_recepcion')
    
    precio_sugerido_min = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Precio mínimo sugerido por kg o unidad")
    precio_sugerido_max = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Precio máximo sugerido por kg o unidad")
    
    history = HistoricalRecords()
    
    
    def __str__(self):
        producto = self.producto.nombre if self.producto else 'Producto'
        return f"Pallet - {producto} ({self.cantidad_cajas} cajas, {self.peso_bruto}kg)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar totales en la recepción principal
        self.recepcion.actualizar_totales()
    
    class Meta:
        verbose_name = _("Reception Detail")
        verbose_name_plural = _("Reception Details")

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
            return f"{base} - Detalle {self.detalle.uid}"
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Solo proceder si la recepción está en estado aprobado
        if instance.estado == "aprobado":
            logger.info(f"Procesando recepción {instance.numero_guia} para crear lotes")
            
            # Procesar solo detalles que no tienen lote creado aún
            detalles_sin_lote = instance.detalles.filter(lote_creado__isnull=True)
            logger.info(f"Encontrados {detalles_sin_lote.count()} detalles sin lote")
            
            # Usar una bandera para evitar recursividad y duplicación
            if not hasattr(instance, '_lotes_creados') or not instance._lotes_creados:
                # Marcar que ya se procesaron los lotes para esta instancia
                instance._lotes_creados = True
                
                for detalle in detalles_sin_lote:
                    try:
                        logger.info(f"Creando lote para detalle {detalle.id} - Producto: {detalle.producto.nombre if detalle.producto else 'No especificado'}")
                        
                        # Crear un nuevo lote de fruta basado en el detalle de recepción
                        lote = FruitLot(
                            producto=detalle.producto,
                            # Preferir la marca del detalle si viene, si no usar la del producto
                            marca=(detalle.marca or (detalle.producto.marca if getattr(detalle, 'producto', None) and getattr(detalle.producto, 'marca', None) else "")),
                            variedad=detalle.variedad or "",
                            proveedor=instance.proveedor if instance.proveedor else None,
                            procedencia=instance.proveedor.direccion if instance.proveedor and instance.proveedor.direccion else "No especificada",
                            pais="Chile",  # Valor por defecto, podría ser un campo en Proveedor
                            calibre=detalle.calibre or "No especificado",
                            box_type=detalle.box_type,
                            cantidad_cajas=detalle.cantidad_cajas,
                            peso_bruto=detalle.peso_bruto,
                            # peso_neto será calculado en FruitLot.save() usando peso_bruto, box_type y pallet_type
                            business=instance.business,
                            fecha_ingreso=instance.fecha_recepcion.date() if instance.fecha_recepcion else None,
                            estado_maduracion=detalle.estado_maduracion or "verde",
                            costo_inicial=detalle.costo,  # Usar el costo del detalle de recepción
                            porcentaje_perdida_estimado=detalle.porcentaje_perdida_estimado,  # Usar el porcentaje de pérdida estimado del detalle
                            # Campos de concesión
                            en_concesion=detalle.en_concesion,
                            comision_por_kilo=detalle.comision_por_kilo,
                            fecha_limite_concesion=detalle.fecha_limite_concesion,
                            # El campo propietario_original espera un objeto Supplier, no un string
                            propietario_original=instance.proveedor if detalle.en_concesion else None,
                            # Precios sugeridos
                            precio_sugerido_min=detalle.precio_sugerido_min,
                            precio_sugerido_max=detalle.precio_sugerido_max,
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
                        logger.info(f"Lote creado automáticamente: {lote} desde recepción {instance.numero_guia}")
                    except Exception as e:
                        logger.error(f"Error al crear lote para detalle {detalle.id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error general al crear lotes para recepción {instance.id}: {str(e)}")

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
        # No asignamos peso_neto desde ReceptionDetail porque no existe en el modelo.
        # FruitLot recalculará peso_neto en save() si corresponde.
        # Sincronizar variedad desde el detalle si existe
        if getattr(instance, 'variedad', None) is not None:
            lote.variedad = instance.variedad
        # Sincronizar marca si viene en el detalle
        if getattr(instance, 'marca', None) is not None:
            lote.marca = instance.marca or (lote.marca or "")
        
        # Actualizar campos de precios sugeridos
        if instance.precio_sugerido_min is not None:
            lote.precio_sugerido_min = instance.precio_sugerido_min
        if instance.precio_sugerido_max is not None:
            lote.precio_sugerido_max = instance.precio_sugerido_max
            
        # Actualizar información de concesión
        lote.en_concesion = instance.en_concesion
        lote.comision_por_kilo = instance.comision_por_kilo
        lote.fecha_limite_concesion = instance.fecha_limite_concesion
        
        # No hay campo temperatura en FruitLot, así que no actualizamos este campo
        
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

class ConcessionSettlement(BaseModel):
    """
    Modelo para registrar liquidaciones de productos vendidos en concesión
    """
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    proveedor = models.ForeignKey('Supplier', on_delete=models.PROTECT, related_name='liquidaciones')
    fecha_liquidacion = models.DateTimeField(default=timezone.now)
    
    # Totales
    total_kilos_vendidos = models.DecimalField(max_digits=10, decimal_places=2)
    total_ventas = models.DecimalField(max_digits=12, decimal_places=2)
    total_comision = models.DecimalField(max_digits=12, decimal_places=2)
    monto_a_liquidar = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Estado
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de pago'),
        ('pagado', 'Pagado'),
        ('cancelado', 'Cancelado'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    
    # Comprobante de pago
    comprobante = models.FileField(upload_to='comprobantes_liquidacion', null=True, blank=True)
    
    # Notas
    notas = models.TextField(blank=True, null=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Liquidación {self.id} - {self.proveedor.nombre} - ${self.monto_a_liquidar:,.0f}"
    
    class Meta:
        verbose_name = _("Concession Settlement")
        verbose_name_plural = _("Concession Settlements")
        ordering = ['-fecha_liquidacion']

class ConcessionSettlementDetail(models.Model):
    """
    Detalle de ventas incluidas en una liquidación de concesión
    """
    liquidacion = models.ForeignKey('ConcessionSettlement', on_delete=models.CASCADE, related_name='detalles')
    venta = models.ForeignKey('sales.Sale', on_delete=models.PROTECT)
    item_venta = models.ForeignKey('sales.SaleItem', on_delete=models.PROTECT)
    lote = models.ForeignKey('FruitLot', on_delete=models.PROTECT)
    
    cantidad_kilos = models.DecimalField(max_digits=8, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    comision = models.DecimalField(max_digits=10, decimal_places=2)
    monto_liquidado = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"Detalle {self.id} - Venta {self.venta.id} - {self.cantidad_kilos}kg"
    
    class Meta:
        verbose_name = _("Concession Settlement Detail")
        verbose_name_plural = _("Concession Settlement Details")

class FruitBin(BaseModel):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    codigo = models.CharField(max_length=50, help_text="Código o identificador del bin")
    producto = models.ForeignKey('Product', on_delete=models.PROTECT)
    variedad = models.CharField(max_length=50, blank=True, null=True)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    # Información de peso
    peso_bruto = models.DecimalField(max_digits=10, decimal_places=2)
    peso_tara = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Persistimos peso_neto para evitar confusiones y facilitar reportes
    peso_neto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                    help_text="Peso neto en kg (peso_bruto - peso_tara)")
    
    # Información de costos
    costo_por_kilo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="Costo por kg del bin")
    costo_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                      help_text="Costo total del bin (opcional; si no se define se calcula)")
    
    # Concesión (para ventas y liquidaciones manuales)
    en_concesion = models.BooleanField(default=False, help_text="Indica si el bin está en concesión")
    comision_por_kilo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                            help_text="Comisión por kilo para bin en concesión")
    fecha_limite_concesion = models.DateField(null=True, blank=True,
                                              help_text="Fecha límite para vender el bin en concesión")
    propietario_original = models.ForeignKey('Supplier', on_delete=models.PROTECT,
                                            related_name='bins_en_concesion',
                                            null=True, blank=True,
                                            help_text="Proveedor propietario original del bin en concesión")
    # Configuración de comisión (persistencia de la forma enviada por el cliente)
    COMISION_BASE_CHOICES = [
        ('kg', 'Por kilo'),
        ('caja', 'Por caja'),
        ('unidad', 'Por unidad'),
        ('venta', 'Por venta'),
    ]
    comision_base = models.CharField(max_length=12, choices=COMISION_BASE_CHOICES, null=True, blank=True)
    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    comision_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Estado de pago al proveedor para este bin (independiente de recepciones)
    pago_pendiente = models.BooleanField(default=False, help_text="Indica si el pago al proveedor por este bin está pendiente")
    
    def save(self, *args, **kwargs):
        """Mantiene peso_neto sincronizado con peso_bruto y peso_tara."""
        try:
            if self.peso_bruto is not None and self.peso_tara is not None:
                self.peso_neto = self.peso_bruto - self.peso_tara
                # Si guardan con update_fields y actualizan bruto/tara, asegurar que peso_neto también se persista
                update_fields = kwargs.get('update_fields')
                if update_fields is not None:
                    try:
                        # update_fields puede venir como set o lista
                        uf = set(update_fields)
                        if 'peso_bruto' in uf or 'peso_tara' in uf:
                            uf.add('peso_neto')
                            kwargs['update_fields'] = list(uf)
                    except Exception:
                        # Si algo falla, no bloquear el save
                        pass
        except Exception:
            pass
        super().save(*args, **kwargs)
    
    @property
    def costo_total_calculado(self):
        """Retorna costo_total si existe; en su defecto calcula costo_por_kilo * peso_neto"""
        try:
            if self.costo_total is not None:
                return self.costo_total
            if self.costo_por_kilo is not None and self.peso_neto is not None:
                return self.costo_por_kilo * self.peso_neto
        except Exception:
            pass
        return None
    
    # Estado y calidad
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('EN_PROCESO', 'En Proceso de Transformación'),
        ('TRANSFORMADO', 'Transformado a Pallets'),
        ('VENDIDO', 'Vendido'),
        ('DESCARTADO', 'Descartado'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='DISPONIBLE')
    # Usar el mismo esquema de calibraje que FruitLot
    CALIDAD_CHOICES = [
        ('DESCARTE', 'Descarte'),
        ('5TA', '5ta'),
        ('4TA', '4ta'),
        ('3RA', '3ra'),
        ('2DA', '2da'),
        ('1RA', '1ra'),
        ('EXTRA', 'Extra'),
        ('SUPER_EXTRA', 'Super Extra'),
    ]
    calidad = models.CharField(max_length=16, choices=CALIDAD_CHOICES, default='3RA')
    
    # Ubicación/locación del bin
    UBICACION_CHOICES = [
        ('BODEGA', 'En bodega'),
        ('PACKING', 'Despachado al packing'),
        ('OTRO', 'Otra locación'),
    ]
    ubicacion = models.CharField(max_length=20, choices=UBICACION_CHOICES, default='BODEGA')
    
    # Información de recepción (opcional)
    recepcion = models.ForeignKey(GoodsReception, on_delete=models.SET_NULL, 
                                null=True, blank=True, related_name='bins')
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    proveedor = models.ForeignKey('Supplier', on_delete=models.PROTECT, null=True, blank=True)
    
    # Campos para trazabilidad
    temperatura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    historial = HistoricalRecords()
    
    def __str__(self):
        return f"Bin {self.codigo} - {self.producto.nombre} ({self.peso_bruto}kg)"
    
    class Meta:
        verbose_name = "Bin de Fruta"
        verbose_name_plural = "Bins de Fruta"
        ordering = ['-fecha_recepcion']

# Importar modelos de trazabilidad bin-lote
from .bin_to_lot_models import BinToLotTransformation, BinToLotTransformationDetail