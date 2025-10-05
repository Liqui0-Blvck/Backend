from rest_framework import serializers
from .models import BoxType, FruitLot, StockReservation, Product, GoodsReception, Supplier, ReceptionDetail, SupplierPayment, ConcessionSettlement, ConcessionSettlementDetail
from accounts.models import Perfil
from sales.models import Customer, SaleItem
from django.db.models import Sum, Max, F
from decimal import Decimal

class BoxTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoxType
        fields = ('uid', 'nombre', 'descripcion', 'peso_caja', 'capacidad_por_caja', 'cantidad_max_cajas', 'business')

class SupplierSerializer(serializers.ModelSerializer):
    """
    Serializador detallado para proveedores que incluye toda la información necesaria
    para mostrar en el frontend, incluyendo recepciones, pagos, liquidaciones y pallets.
    """
    # Campos calculados básicos
    total_deuda = serializers.SerializerMethodField()
    total_pagado = serializers.SerializerMethodField()
    recepciones_pendientes = serializers.SerializerMethodField()
    
    # Campos para contadores y resúmenes
    cantidad_recepciones = serializers.SerializerMethodField()
    cantidad_liquidaciones = serializers.SerializerMethodField()
    cantidad_pallets = serializers.SerializerMethodField()
    cantidad_cajas = serializers.SerializerMethodField()
    total_kg_recepcionados = serializers.SerializerMethodField()
    
    # Campos para últimas actividades
    ultima_recepcion = serializers.SerializerMethodField()
    ultima_liquidacion = serializers.SerializerMethodField()
    ultimo_pago = serializers.SerializerMethodField()
    
    # Campos para detalles de pallets
    detalle_pallets = serializers.SerializerMethodField()
    
    # Campos para análisis financiero
    resumen_pagos = serializers.SerializerMethodField()
    resumen_liquidaciones = serializers.SerializerMethodField()
    # Flag de vinculación a usuario
    vinculado = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = ('uid', 'nombre', 'rut', 'direccion', 'telefono', 'email', 'contacto', 'observaciones', 
                 'business', 'activo', 'created_at', 'updated_at',
                 'total_deuda', 'total_pagado', 'recepciones_pendientes',
                 'cantidad_recepciones', 'cantidad_liquidaciones', 'cantidad_pallets', 'cantidad_cajas',
                 'total_kg_recepcionados', 'ultima_recepcion', 'ultima_liquidacion', 'ultimo_pago',
                 'detalle_pallets', 'resumen_pagos', 'resumen_liquidaciones', 'vinculado')
    
    def get_total_deuda(self, obj):
        # Calcular el total de deuda sumando los montos totales solo de las recepciones pendientes de pago
        total = obj.recepciones.filter(estado_pago='pendiente').aggregate(total=Sum('monto_total'))['total'] or 0
        
        # Restar los pagos realizados para las recepciones pendientes
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj, recepcion__estado_pago='pendiente')
        total_pagado = pagos.aggregate(total=Sum('monto'))['total'] or 0
        
        return total - total_pagado
        
    def get_total_pagado(self, obj):
        """Suma todos los pagos realizados al proveedor"""
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj)
        return pagos.aggregate(total=Sum('monto'))['total'] or 0
    
    def get_recepciones_pendientes(self, obj):
        """Retorna las últimas 5 recepciones del proveedor con su estado"""
        # Obtener todas las recepciones del proveedor, ordenadas por fecha (más recientes primero)
        recepciones = obj.recepciones.all().order_by('-fecha_recepcion')[:5]
        
        # Lista para almacenar las recepciones
        lista_recepciones = []
        
        for recepcion in recepciones:
            # Calcular el monto total de la recepción
            monto_total = recepcion.monto_total or 0
            
            # Calcular el total pagado para esta recepción
            pagos = recepcion.pagos.aggregate(total=Sum('monto'))['total'] or 0
            
            # Calcular saldo pendiente (si está pagado, el saldo es 0)
            saldo_pendiente = 0 if recepcion.estado_pago == 'pagado' else (monto_total - pagos)
            
            # Agregar a la lista con el estado incluido
            lista_recepciones.append({
                'uid': recepcion.uid,
                'numero_guia': recepcion.numero_guia,
                'fecha_recepcion': recepcion.fecha_recepcion,
                'monto_total': monto_total,
                'monto_pagado': pagos if recepcion.estado_pago == 'pendiente' else monto_total,
                'saldo_pendiente': saldo_pendiente,
                'estado_pago': recepcion.estado_pago
            })
        
        return lista_recepciones
    
    def get_cantidad_recepciones(self, obj):
        """Retorna el número total de recepciones del proveedor"""
        return obj.recepciones.count()
    
    def get_cantidad_liquidaciones(self, obj):
        """Retorna el número total de liquidaciones del proveedor"""
        return obj.liquidaciones.count()
    
    def get_cantidad_pallets(self, obj):
        """Retorna el número total de pallets recibidos del proveedor"""
        return sum(recepcion.total_pallets for recepcion in obj.recepciones.all())
    
    def get_cantidad_cajas(self, obj):
        """Retorna el número total de cajas recibidas del proveedor"""
        return sum(recepcion.total_cajas for recepcion in obj.recepciones.all())
    
    def get_total_kg_recepcionados(self, obj):
        """Retorna el total de kilogramos recibidos del proveedor"""
        return sum(recepcion.total_peso_bruto for recepcion in obj.recepciones.all())
    
    def get_ultima_recepcion(self, obj):
        """Retorna la información de la última recepción del proveedor"""
        ultima = obj.recepciones.order_by('-fecha_recepcion').first()
        if ultima:
            return {
                'uid': ultima.uid,
                'numero_guia': ultima.numero_guia,
                'fecha_recepcion': ultima.fecha_recepcion,
                'monto_total': ultima.monto_total,
                'total_pallets': ultima.total_pallets,
                'total_cajas': ultima.total_cajas
            }
        return None
    
    def get_ultima_liquidacion(self, obj):
        """Retorna la información de la última liquidación del proveedor"""
        ultima = obj.liquidaciones.order_by('-fecha_liquidacion').first()
        if ultima:
            return {
                'uid': ultima.uid,
                'fecha_liquidacion': ultima.fecha_liquidacion,
                'total_kilos_vendidos': ultima.total_kilos_vendidos,
                'total_ventas': ultima.total_ventas,
                'monto_a_liquidar': ultima.monto_a_liquidar,
                'estado': ultima.estado
            }
        return None
    
    def get_ultimo_pago(self, obj):
        """Retorna la información del último pago realizado al proveedor"""
        ultimo = SupplierPayment.objects.filter(recepcion__proveedor=obj).order_by('-fecha_pago').first()
        if ultimo:
            return {
                'uid': ultimo.uid,
                'fecha_pago': ultimo.fecha_pago,
                'monto': ultimo.monto,
                'metodo_pago': ultimo.metodo_pago,
                'recepcion': ultimo.recepcion.numero_guia
            }
        return None
    
    def get_detalle_pallets(self, obj):
        """Retorna información detallada de los pallets recibidos del proveedor"""
        # Obtener todas las recepciones del proveedor
        recepciones = obj.recepciones.all()
        
        # Lista para almacenar los detalles de pallets
        detalles = []
        
        for recepcion in recepciones:
            for detalle in recepcion.detalles.all():
                detalles.append({
                    'uid': detalle.uid,
                    'numero_pallet': detalle.numero_pallet,
                    'producto': detalle.producto.nombre if detalle.producto else 'No especificado',
                    'calibre': detalle.calibre or 'No especificado',
                    'cantidad_cajas': detalle.cantidad_cajas,
                    'peso_bruto': detalle.peso_bruto,
                    # ReceptionDetail no tiene campo peso_neto; usar el del lote si existe
                    # o estimar como peso_bruto - peso_tara
                    'peso_neto': (
                        float(detalle.lote_creado.peso_neto) if getattr(detalle, 'lote_creado', None) and getattr(detalle.lote_creado, 'peso_neto', None) is not None
                        else max(float(detalle.peso_bruto or 0) - float(getattr(detalle, 'peso_tara', 0) or 0), 0)
                    ),
                    'calidad': detalle.get_calidad_display(),
                    'fecha_recepcion': recepcion.fecha_recepcion,
                    'numero_guia': recepcion.numero_guia,
                    'lote_id': detalle.lote_creado.id if detalle.lote_creado else None
                })
        
        return detalles
    
    def get_resumen_pagos(self, obj):
        """Retorna un resumen de los pagos realizados al proveedor"""
        # Obtener todos los pagos del proveedor
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj).order_by('-fecha_pago')
        
        # Lista para almacenar los pagos
        lista_pagos = []
        
        for pago in pagos:
            lista_pagos.append({
                'uid': pago.uid,
                'fecha_pago': pago.fecha_pago,
                'monto': pago.monto,
                'metodo_pago': pago.get_metodo_pago_display(),
                'recepcion': pago.recepcion.numero_guia,
                'notas': pago.notas
            })
        
        return lista_pagos
    
    def get_resumen_liquidaciones(self, obj):
        """Retorna un resumen de las liquidaciones del proveedor"""
        # Obtener todas las liquidaciones del proveedor
        liquidaciones = obj.liquidaciones.all().order_by('-fecha_liquidacion')
        
        # Lista para almacenar las liquidaciones
        lista_liquidaciones = []
        
        for liquidacion in liquidaciones:
            # Obtener detalles de la liquidación
            detalles = []
            for detalle in liquidacion.detalles.all():
                detalles.append({
                    'venta_id': detalle.venta.id,
                    'lote_id': detalle.lote.id,
                    'cantidad_kilos': detalle.cantidad_kilos,
                    'precio_venta': detalle.precio_venta,
                    'comision': detalle.comision,
                    'monto_liquidado': detalle.monto_liquidado
                })
            
            lista_liquidaciones.append({
                'uid': liquidacion.uid,
                'fecha_liquidacion': liquidacion.fecha_liquidacion,
                'total_kilos_vendidos': liquidacion.total_kilos_vendidos,
                'total_ventas': liquidacion.total_ventas,
                'total_comision': liquidacion.total_comision,
                'monto_a_liquidar': liquidacion.monto_a_liquidar,
                'estado': liquidacion.get_estado_display(),
                'detalles': detalles
            })
        
        return lista_liquidaciones

    def get_vinculado(self, obj):
        """Retorna True si existe un Perfil vinculado a este proveedor"""
        try:
            return Perfil.objects.filter(proveedor=obj).exists()
        except Exception:
            return False
    
    def get_cantidad_recepciones(self, obj):
        """Retorna el número total de recepciones del proveedor"""
        return obj.recepciones.count()
    
    def get_ultima_recepcion(self, obj):
        """Retorna información sobre la última recepción del proveedor"""
        ultima = obj.recepciones.order_by('-fecha_recepcion').first()
        if not ultima:
            return None
            
        return {
            'uid': str(ultima.uid),
            'numero_guia': ultima.numero_guia,
            'fecha_recepcion': ultima.fecha_recepcion,
            'monto_total': float(ultima.monto_total)
        }
    
    def get_cantidad_liquidaciones(self, obj):
        """Retorna el número total de liquidaciones del proveedor"""
        return obj.liquidaciones.count()
    
    def get_ultima_liquidacion(self, obj):
        """Retorna información sobre la última liquidación del proveedor"""
        ultima = obj.liquidaciones.order_by('-fecha_liquidacion').first()
        if not ultima:
            return None
            
        return {
            'uid': str(ultima.uid),
            'fecha_liquidacion': ultima.fecha_liquidacion,
            'monto_a_liquidar': float(ultima.monto_a_liquidar),
            'estado': ultima.estado,
            'estado_display': ultima.get_estado_display()
        }

class SupplierSerializerList(serializers.ModelSerializer):
    """
    Serializador simplificado para listar proveedores con información resumida.
    Optimizado para rendimiento en listados con muchos proveedores.
    """
    total_deuda = serializers.SerializerMethodField()
    total_pagado = serializers.SerializerMethodField()
    recepciones_count = serializers.SerializerMethodField()
    liquidaciones_count = serializers.SerializerMethodField()
    ultima_actividad = serializers.SerializerMethodField()
    vinculado = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = (
            'uid', 'nombre', 'rut', 'telefono', 'email', 'contacto', 
            'activo', 'total_deuda', 'total_pagado', 'recepciones_count',
            'liquidaciones_count', 'ultima_actividad', 'vinculado'
        )
    
    def get_total_deuda(self, obj):
        """Calcula la deuda total pendiente del proveedor"""
        # Calcular el total de deuda sumando los montos totales solo de las recepciones pendientes de pago
        total = obj.recepciones.filter(estado_pago='pendiente').aggregate(total=Sum('monto_total'))['total'] or 0
        
        # Restar los pagos realizados para las recepciones pendientes
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj, recepcion__estado_pago='pendiente')
        total_pagado = pagos.aggregate(total=Sum('monto'))['total'] or 0
        
        return total - total_pagado
    
    def get_total_pagado(self, obj):
        """Suma todos los pagos realizados al proveedor"""
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj)
        return pagos.aggregate(total=Sum('monto'))['total'] or 0
    
    def get_recepciones_count(self, obj):
        """Retorna el número total de recepciones del proveedor"""
        return obj.recepciones.count()
    
    def get_liquidaciones_count(self, obj):
        """Retorna el número total de liquidaciones del proveedor"""
        return obj.liquidaciones.count()
    
    def get_ultima_actividad(self, obj):
        """Determina la fecha de última actividad (recepción o liquidación)"""
        ultima_recepcion = obj.recepciones.aggregate(ultima=Max('fecha_recepcion'))['ultima']
        ultima_liquidacion = obj.liquidaciones.aggregate(ultima=Max('fecha_liquidacion'))['ultima']
        
        # Determinar cuál es la más reciente
        if ultima_recepcion and ultima_liquidacion:
            return max(ultima_recepcion, ultima_liquidacion)
        elif ultima_recepcion:
            return ultima_recepcion
        elif ultima_liquidacion:
            return ultima_liquidacion
        else:
            return None

    def get_vinculado(self, obj):
        """Retorna True si existe un Perfil vinculado a este proveedor"""
        try:
            return Perfil.objects.filter(proveedor=obj).exists()
        except Exception:
            return False

class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    unidad = serializers.SerializerMethodField()
    
    def get_unidad(self, obj):
        return obj.get_unidad_display()
    
    class Meta:
        model = Product
        fields = ('uid', 'nombre', 'marca', 'unidad', 'business', 'activo', 'image_path', 'image_url')
    
    def get_image_url(self, obj):
        if obj.image_path and hasattr(obj.image_path, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.image_path.url)
            return obj.image_path.url
        return None

class FruitLotListSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    tipo_producto = serializers.CharField(source='producto.tipo_producto', read_only=True)
    # Campos para stock disponible
    cajas_disponibles = serializers.SerializerMethodField()
    costo_total_pallet = serializers.SerializerMethodField()
    proveedor = serializers.CharField(source='proveedor.nombre', read_only=True)
    peso_reservado = serializers.SerializerMethodField()
    # Peso del BoxType (explícito)
    box_type_peso_caja = serializers.SerializerMethodField()
    # Campos informativos (solo lectura)
    kg_por_caja_estimada = serializers.SerializerMethodField()
    tara_por_caja_kg = serializers.SerializerMethodField()
    kg_bruto_por_caja_estimada = serializers.SerializerMethodField()
    codigo = serializers.CharField(source='qr_code', read_only=True)

    class Meta:
        model = FruitLot
        fields = (
            'uid', 'producto', 'producto_nombre', 'tipo_producto', 'calibre', 'variedad', 'codigo',
            'peso_bruto', 'peso_neto', 'peso_reservado', 'cajas_disponibles','estado_maduracion', 'estado_lote', 'fecha_ingreso', 
            'procedencia', 'proveedor', 'costo_inicial', 'en_concesion', 'costo_total_pallet', 'proveedor',
            # Informativos
            'kg_por_caja_estimada', 'tara_por_caja_kg', 'kg_bruto_por_caja_estimada', 'box_type_peso_caja',
        )

    def _get_active_reservations_sum(self, obj):
        if not hasattr(obj, '_active_reservations_sum_list'):
            obj._active_reservations_sum_list = StockReservation.objects.filter(
                lote=obj, estado='en_proceso'
            ).aggregate(
                total_cajas=Sum('cajas_reservadas'),
                total_kg=Sum('kg_reservados'),
                total_unidades=Sum('unidades_reservadas')
            )
        return obj._active_reservations_sum_list

    def get_cajas_disponibles(self, obj):
        sums = self._get_active_reservations_sum(obj)
        cajas_reservadas = sums.get('total_cajas') or 0
        return obj.cantidad_cajas - cajas_reservadas
    
    def get_peso_reservado(self, obj):
        # Solo aplica para productos tipo palta
        if not obj.producto or obj.producto.tipo_producto != 'palta':
            return 0
        sums = self._get_active_reservations_sum(obj)
        return float(sums.get('total_kg') or 0)
    
    def get_tipo_producto(self, obj):
        if obj.producto:
            return obj.producto.tipo_producto
        return 'otro'
    
    def get_costo_total_pallet(self, obj):
        if not obj.producto:
            return 0
        
        # Acceder al tipo_producto a través de la relación con el producto.
        if obj.producto.tipo_producto == 'palta':
            # Usar el peso neto INICIAL del pallet y el costo unitario inicial
            peso_inicial = self.get_peso_neto_inicial(obj)
            costo_unitario_inicial = obj.costo_inicial or 0
            return float(peso_inicial) * float(costo_unitario_inicial)
        else:
            # Usar la cantidad de cajas INICIAL al crear el pallet
            cantidad_cajas = self.get_cantidad_cajas_inicial(obj)
            costo_inicial = obj.costo_inicial or 0
            return float(cantidad_cajas) * float(costo_inicial)

    def get_disponibilidad(self, obj):
        if not obj.producto:
            return 0
            
        if obj.producto.tipo_producto == 'palta':
            return obj.peso_disponible()
        else:
            return obj.unidades_disponibles()

    def get_cantidad_cajas_inicial(self, obj):
        """Cantidad de cajas al momento de creación del pallet, desde el primer snapshot del historial."""
        try:
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primero = historial.first()
                return int(getattr(primero, 'cantidad_cajas', obj.cantidad_cajas) or 0)
        except Exception:
            pass
        return int(obj.cantidad_cajas or 0)

    def get_peso_neto_inicial(self, obj):
        """Peso neto al momento de creación del pallet, desde el primer snapshot del historial."""
        try:
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primero = historial.first()
                return float(getattr(primero, 'peso_neto', obj.peso_neto) or 0)
        except Exception:
            pass
        return float(obj.peso_neto or 0)

    # --------- Campos informativos ---------
    def get_kg_por_caja_estimada(self, obj):
        try:
            if obj.cantidad_cajas and obj.cantidad_cajas > 0 and obj.peso_neto:
                return round(float(obj.peso_neto) / float(obj.cantidad_cajas), 2)
        except Exception:
            pass
        return None

    def get_tara_por_caja_kg(self, obj):
        try:
            if obj.box_type and obj.box_type.peso_caja is not None:
                return float(obj.box_type.peso_caja)
        except Exception:
            pass
        return None

    def get_kg_bruto_por_caja_estimada(self, obj):
        kg = self.get_kg_por_caja_estimada(obj)
        tara = self.get_tara_por_caja_kg(obj)
        if kg is not None and tara is not None:
            return round(kg + tara, 2)
        return None

    def get_box_type_peso_caja(self, obj):
        """Retorna explícitamente el peso de la caja del BoxType asociado."""
        try:
            if obj.box_type and obj.box_type.peso_caja is not None:
                return float(obj.box_type.peso_caja)
        except Exception:
            pass
        return None

class FruitLotSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.SerializerMethodField()
    box_type_nombre = serializers.SerializerMethodField()
    pallet_type_nombre = serializers.SerializerMethodField()
    costo_actual = serializers.SerializerMethodField()
    peso_reservado = serializers.SerializerMethodField()
    peso_disponible = serializers.SerializerMethodField()
    dias_desde_ingreso = serializers.SerializerMethodField()
    dinero_generado = serializers.SerializerMethodField()
    porcentaje_vendido = serializers.SerializerMethodField()
    propietario_original_nombre = serializers.SerializerMethodField()
    proveedor_nombre = serializers.SerializerMethodField()
    proveedor_uid = serializers.SerializerMethodField()
    info_producto = serializers.SerializerMethodField()
    detalles_lote = serializers.SerializerMethodField()
    
    def get_detalles_lote(self, obj):
        """Retorna una versión simplificada de los detalles del lote"""
        tipo_producto = self.get_tipo_producto(obj)
        
        detalles = {
            'uid': str(obj.uid),
            'producto_nombre': self.get_producto_nombre(obj),
            'tipo_producto': tipo_producto,
            'calibre': obj.calibre,
            'box_type': self.get_box_type_nombre(obj),
            'cantidad_cajas': obj.cantidad_cajas,
            'estado_lote': obj.estado_lote,
            'estado_maduracion': obj.estado_maduracion,
            'fecha_ingreso': obj.fecha_ingreso.isoformat() if obj.fecha_ingreso else None,
            'costo_inicial': float(obj.costo_inicial) if obj.costo_inicial else 0,
            'costo_actual': float(self.get_costo_actual(obj)),
        }
        
        # Agregar campos específicos según el tipo de producto
        if tipo_producto == 'palta':
            detalles.update({
                'peso_bruto': float(obj.peso_bruto) if obj.peso_bruto else 0,
                'peso_neto': float(obj.peso_neto) if obj.peso_neto else 0,
                'peso_disponible': float(self.get_kg_disponibles(obj)),
                'peso_reservado': float(self.get_peso_reservado(obj)),
            })
        elif tipo_producto == 'otro':
            detalles.update({
                'cantidad_unidades': obj.cantidad_unidades,
                'unidades_por_caja': obj.unidades_por_caja,
                'unidades_disponibles': self.get_unidades_disponibles(obj),
                'unidades_reservadas': obj.unidades_reservadas,
            })
            
        return detalles

    # Campos para stock disponible
    cajas_disponibles = serializers.SerializerMethodField()
    kg_disponibles = serializers.SerializerMethodField()
    unidades_disponibles = serializers.SerializerMethodField()
    # Campos informativos (solo lectura)
    kg_por_caja_estimada = serializers.SerializerMethodField()
    tara_por_caja_kg = serializers.SerializerMethodField()
    kg_bruto_por_caja_estimada = serializers.SerializerMethodField()

    class Meta:
        model = FruitLot
        fields = (
            'uid', 'producto', 'marca', 'variedad', 'proveedor', 'procedencia', 'pais', 'calibre', 'box_type', 'pallet_type',
            'cantidad_cajas', 'peso_neto', 'cantidad_unidades', 'costo_inicial', 'fecha_ingreso',
            'estado_lote', 'estado_maduracion', 'en_concesion', 'comision_por_kilo', 'fecha_limite_concesion',
            'propietario_original', 
            # SerializerMethodFields
            'producto_nombre', 'box_type_nombre', 'pallet_type_nombre', 'costo_actual', 'proveedor_nombre',
            'dias_desde_ingreso', 'dinero_generado', 'porcentaje_vendido', 'propietario_original_nombre',
            'info_producto', 'cajas_disponibles', 'kg_disponibles', 'peso_disponible', 'peso_reservado', 
            'unidades_disponibles', 'detalles_lote', 'proveedor_uid',
            # Informativos
            'kg_por_caja_estimada', 'tara_por_caja_kg', 'kg_bruto_por_caja_estimada',
        )

    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if obj.proveedor else None
        
    def get_proveedor_uid(self, obj):
        return str(obj.proveedor.uid) if obj.proveedor else None

    def get_dias_desde_ingreso(self, obj):
        from django.utils import timezone
        if obj.fecha_ingreso:
            return (timezone.now().date() - obj.fecha_ingreso).days
        return 0

    def get_tipo_producto(self, obj):
        if obj.producto:
            return obj.producto.tipo_producto
        return None

    def get_info_producto(self, obj):
        """
        Proporciona información detallada y estructurada según el tipo de producto
        """
        tipo = self.get_tipo_producto(obj)
        
        # Información común para todos los tipos de producto
        info = {
            'tipo': tipo,
            'nombre': self.get_producto_nombre(obj),
            'estado_lote': obj.estado_lote,
            'dias_desde_ingreso': self.get_dias_desde_ingreso(obj),
            'costo_inicial': float(obj.costo_inicial) if obj.costo_inicial else 0,
            'costo_actual': float(self.get_costo_actual(obj)),
            'en_concesion': obj.en_concesion,
        }
        
        # Información específica para paltas
        if tipo == 'palta':
            info.update({
                'calibre': obj.calibre,
                'estado_maduracion': obj.estado_maduracion,
                'fecha_maduracion': obj.fecha_maduracion.isoformat() if obj.fecha_maduracion else None,
                'peso': {
                    'bruto': float(obj.peso_bruto) if obj.peso_bruto else 0,
                    'neto': float(obj.peso_neto) if obj.peso_neto else 0,
                    'disponible': float(self.get_kg_disponibles(obj)),
                    'reservado': float(obj.peso_neto - self.get_kg_disponibles(obj)),
                    'vendido': float(self.get_peso_vendido(obj)),
                    'porcentaje_vendido': float(self.get_porcentaje_vendido(obj)),
                },
                'perdida': {
                    'porcentaje': self.get_porcentaje_perdida(obj),
                    'estimada_kg': self.get_perdida_estimada(obj),
                    'valor': self.get_valor_perdida(obj),
                },
                'precios': {
                    'costo_kg': self.get_costo_real_kg(obj),
                    'recomendado_kg': self.get_precio_recomendado_kg(obj),
                    'ganancia_kg': self.get_ganancia_kg(obj),
                    'margen': self.get_margen(obj),
                    'sugerido_min': float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None,
                    'sugerido_max': float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None,
                },
                'proyecciones': {
                    'ingreso_estimado': self.get_ingreso_estimado(obj),
                    'ganancia_total': self.get_ganancia_total(obj),
                },
                'urgencia': self.get_urgencia_venta(obj),
            })
            
            # Si está en concesión, agregar información específica
            if obj.en_concesion:
                info['concesion'] = {
                    'propietario': self.get_propietario_original_nombre(obj),
                    'comision_por_kilo': float(obj.comision_por_kilo) if obj.comision_por_kilo else 0,
                    'fecha_limite': obj.fecha_limite_concesion.isoformat() if obj.fecha_limite_concesion else None,
                }
        
        # Información específica para otros productos
        else:
            info.update({
                'cantidad': {
                    'cajas': obj.cantidad_cajas,
                    'unidades_por_caja': getattr(obj, 'unidades_por_caja', 0),
                    'unidades_totales': getattr(obj, 'cantidad_unidades', 0),
                    'unidades_disponibles': getattr(obj, 'unidades_disponibles', lambda: 0)(),
                    'unidades_reservadas': getattr(obj, 'unidades_reservadas', 0),
                },
                'precios': {
                    'costo_por_caja': float(obj.costo_inicial) if obj.costo_inicial else 0,
                    'costo_total': self.get_costo_total_pallet(obj),
                    'sugerido_min': float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None,
                    'sugerido_max': float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None,
                }
            })
            
            # Si está en concesión, agregar información específica
            if obj.en_concesion:
                info['concesion'] = {
                    'propietario': self.get_propietario_original_nombre(obj),
                    'fecha_limite': obj.fecha_limite_concesion.isoformat() if obj.fecha_limite_concesion else None,
                }
        
        return info

    def get_producto_nombre(self, obj):
        if obj.producto:
            return obj.producto.nombre
        return None

    def get_box_type_nombre(self, obj):
        if obj.box_type:
            return obj.box_type.nombre
        return None

    def get_pallet_type_nombre(self, obj):
        if obj.pallet_type:
            return obj.pallet_type.nombre
        return None

    def get_costo_actual(self, obj):
        return obj.costo_actualizado()

    def get_peso_reservado(self, obj):
        from inventory.models import StockReservation
        reservas = StockReservation.objects.filter(lote=obj, estado='en_proceso').aggregate(total_kg=Sum('kg_reservados'))
        return reservas['total_kg'] or 0

    def get_peso_disponible(self, obj):
        # Usar Decimal para evitar mezclar float y Decimal
        from decimal import Decimal as D
        neto = D(obj.peso_neto or 0)
        reservado_raw = self.get_peso_reservado(obj)
        try:
            reservado = D(reservado_raw)
        except Exception:
            reservado = D(str(reservado_raw or 0))
        disponible = neto - reservado
        if disponible < D('0'):
            disponible = D('0')
        return float(disponible)

    def get_tipo_producto(self, obj):
        if not obj.producto:
            return 'otro'
        return obj.producto.tipo_producto

    def get_dias_desde_ingreso(self, obj):
        from django.utils import timezone
        if obj.fecha_ingreso:
            return (timezone.now().date() - obj.fecha_ingreso).days
        return 0

    def get_dias_en_bodega(self, obj):
        return self.get_dias_desde_ingreso(obj)

    def get_porcentaje_perdida(self, obj):
        tipo = self.get_tipo_producto(obj)
        estado = getattr(obj, 'estado_maduracion', 'verde')
        if tipo == 'palta':
            if estado == 'verde':
                return 2
            if estado == 'pre-maduro':
                return 3
            if estado == 'maduro':
                return 5
            if estado == 'sobremaduro':
                return 10
        return 0

    def get_perdida_estimada(self, obj):
        neto = float(obj.peso_neto or 0)
        return round(neto * (self.get_porcentaje_perdida(obj)/100), 2)

    def get_valor_perdida(self, obj):
        perdida = self.get_perdida_estimada(obj)
        costo_actual = float(self.get_costo_actual(obj) or 0)
        return round(perdida * costo_actual, 2)

    # Método get_peso_vendible eliminado - usando peso_neto o peso_disponible directamente

    def get_precio_recomendado_kg(self, obj):
        costo_real = self.get_costo_real_kg(obj)
        return round(costo_real * 1.3, 2)

    def get_costo_real_kg(self, obj):
        return float(obj.costo_inicial or 0)

    def get_ganancia_kg(self, obj):
        return round(self.get_precio_recomendado_kg(obj) - self.get_costo_real_kg(obj), 2)

    def get_margen(self, obj):
        costo = self.get_costo_real_kg(obj)
        if costo > 0:
            return round((self.get_ganancia_kg(obj) / costo) * 100, 2)
        return 25.0

    def get_ingreso_estimado(self, obj):
        # Usar peso_disponible en lugar de peso_vendible
        disponible = self.get_peso_disponible(obj)
        perdida = self.get_perdida_estimada(obj)
        peso_real = round(disponible - perdida if disponible > perdida else 0, 2)
        return round(self.get_precio_recomendado_kg(obj) * peso_real, 2)

    def get_ganancia_total(self, obj):
        # Usar peso_disponible en lugar de peso_vendible
        disponible = self.get_peso_disponible(obj)
        perdida = self.get_perdida_estimada(obj)
        peso_real = round(disponible - perdida if disponible > perdida else 0, 2)
        return round(self.get_ganancia_kg(obj) * peso_real, 2)

    # --------- Campos informativos ---------
    def get_kg_por_caja_estimada(self, obj):
        try:
            if obj.cantidad_cajas and obj.cantidad_cajas > 0 and obj.peso_neto:
                return round(float(obj.peso_neto) / float(obj.cantidad_cajas), 2)
        except Exception:
            pass
        return None

    def get_tara_por_caja_kg(self, obj):
        try:
            if obj.box_type and obj.box_type.peso_caja is not None:
                return float(obj.box_type.peso_caja)
        except Exception:
            pass
        return None

    def get_kg_bruto_por_caja_estimada(self, obj):
        kg = self.get_kg_por_caja_estimada(obj)
        tara = self.get_tara_por_caja_kg(obj)
        if kg is not None and tara is not None:
            return round(kg + tara, 2)
        return None

    def get_resumen_producto(self, obj):
        tipo = self.get_tipo_producto(obj)
        if tipo == 'palta':
            return f"Palta {obj.calibre or 'S/C'} | ${self.get_costo_real_kg(obj):,.0f}/kg | ${self.get_precio_recomendado_kg(obj):,.0f}/kg rec. | {getattr(obj, 'estado_maduracion', '').capitalize()}"
        return None

    def get_urgencia_venta(self, obj):
        estado = getattr(obj, 'estado_maduracion', 'verde')
        if estado == 'maduro':
            return 'alta'
        if estado == 'sobremaduro':
            return 'critica'
        return 'baja'

    def get_recomendacion(self, obj):
        estado = getattr(obj, 'estado_maduracion', 'verde')
        precio = self.get_precio_recomendado_kg(obj)
        if estado == 'verde':
            return {
                'accion': 'esperar',
                'mensaje': 'Mantener en cámara de maduración controlada. Revisar en 3 días.',
                'precio_sugerido': precio
            }
        elif estado == 'pre-maduro':
            return {
                'accion': 'preparar_venta',
                'mensaje': 'Preparar para venta en 2 días.',
                'precio_sugerido': precio
            }
        elif estado == 'maduro':
            return {
                'accion': 'vender',
                'mensaje': 'Vender lo antes posible.',
                'precio_sugerido': precio
            }
        elif estado == 'sobremaduro':
            return {
                'accion': 'liquidar',
                'mensaje': 'Liquidar stock urgentemente.',
                'precio_sugerido': precio
            }
        return None

    def get_costo_total_pallet(self, obj):
        # Calcular el costo total del pallet según su tipo
        if not obj.producto:
            return 0
            
        if obj.producto.tipo_producto == 'palta':
            return round(float(obj.peso_neto or 0) * float(obj.costo_inicial or 0), 2)
        else:  # tipo 'otro'
            return round(float(obj.cantidad_cajas or 0) * float(obj.costo_inicial or 0), 2)
        
    def get_peso_vendido(self, obj):
        # Importar Sale aquí para evitar importaciones circulares
        from sales.models import Sale, SaleItem
        # Sumar el peso vendido de todas las ventas asociadas a este lote
        total_vendido = SaleItem.objects.filter(lote=obj).aggregate(total=Sum('peso_vendido'))['total'] or 0
        return float(total_vendido)
    
    def get_dinero_generado(self, obj):
        # Importar Sale aquí para evitar importaciones circulares
        from sales.models import SaleItem
        # Usar el ID del lote en lugar de la relación directa
        total_dinero = SaleItem.objects.filter(lote=obj).aggregate(total=Sum('subtotal'))['total'] or 0
        return float(total_dinero)
    
    def get_porcentaje_vendido(self, obj):
        """Calcula el porcentaje del lote que ya ha sido vendido"""
        # Proteger cuando peso_neto es None o no positivo
        try:
            from decimal import Decimal as D
            neto = D(str(obj.peso_neto or 0))
            if neto <= 0:
                return 0
            vendido = D(str(self.get_peso_vendido(obj) or 0))
            return round(float((vendido / neto) * 100), 2)
        except Exception:
            # En caso de cualquier problema de tipo/conversión, retornar 0 como valor seguro
            return 0
        
    def get_propietario_original_nombre(self, obj):
        """Obtiene el nombre del propietario original para lotes en concesión"""
        if obj.en_concesion and obj.propietario_original:
            return obj.propietario_original.nombre
        return None

    def _get_active_reservations_sum(self, obj):
        if not hasattr(obj, '_active_reservations_sum'):
            obj._active_reservations_sum = StockReservation.objects.filter(
                lote=obj, estado='en_proceso'
            ).aggregate(
                total_cajas=Sum('cajas_reservadas'),
                total_kg=Sum('kg_reservados'),
                total_unidades=Sum('unidades_reservadas')
            )
        return obj._active_reservations_sum

    def get_cajas_disponibles(self, obj):
        sums = self._get_active_reservations_sum(obj)
        cajas_reservadas = sums.get('total_cajas') or 0
        return obj.cantidad_cajas - cajas_reservadas

    def get_kg_disponibles(self, obj):
        if obj.producto.tipo_producto != 'palta':
            return obj.peso_neto
        sums = self._get_active_reservations_sum(obj)
        kg_reservados = sums.get('total_kg') or 0
        return obj.peso_neto - kg_reservados

    def get_unidades_disponibles(self, obj):
        if obj.producto.tipo_producto == 'palta':
            return obj.cantidad_unidades
        sums = self._get_active_reservations_sum(obj)
        unidades_reservadas = sums.get('total_unidades') or 0
        return obj.cantidad_unidades - unidades_reservadas

class StockReservationSerializer(serializers.ModelSerializer):
    lote_producto = serializers.SerializerMethodField()
    lote_calibre = serializers.SerializerMethodField()
    usuario_nombre = serializers.SerializerMethodField()
    cliente_nombre = serializers.SerializerMethodField()

    class Meta:
        model = StockReservation
        fields = (
            'uid', 'lote', 'usuario', 'cantidad_kg', 'cantidad_cajas', 'cliente', 'nombre_cliente', 'rut_cliente',
            'telefono_cliente', 'email_cliente', 'estado', 'timeout_minutos', 'business',
            'lote_producto', 'lote_calibre', 'usuario_nombre', 'cliente_nombre',
        )
    
    def get_lote_producto(self, obj):
        if obj.lote and obj.lote.producto:
            return obj.lote.producto.nombre
        return None
    
    def get_lote_calibre(self, obj):
        if obj.lote:
            return obj.lote.calibre
        return None
    
    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return f"{obj.usuario.first_name} {obj.usuario.last_name}".strip() or obj.usuario.username
        return None
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        elif obj.nombre_cliente:
            return obj.nombre_cliente
        return None

class ReceptionDetailSerializer(serializers.ModelSerializer):
    recepcion = serializers.SlugRelatedField(queryset=GoodsReception.objects.all(), slug_field='uid', required=False, allow_null=True)
    producto = serializers.SlugRelatedField(queryset=Product.objects.all(), slug_field='uid')
    producto_nombre = serializers.SerializerMethodField()
    box_type = serializers.SlugRelatedField(queryset=BoxType.objects.all(), slug_field='uid', required=False, allow_null=True)
    
    def get_producto_nombre(self, obj):
        if obj.producto:
            return obj.producto.nombre
        return None
        
    class Meta:
        model = ReceptionDetail
        fields = (
            'uid', 'recepcion', 'producto', 'producto_nombre', 'variedad', 'calibre', 'box_type', 'cantidad_cajas', 'peso_bruto',
            'peso_tara', 'calidad', 'temperatura', 'estado_maduracion',
            'costo', 'porcentaje_perdida_estimado',
            'precio_sugerido_min', 'precio_sugerido_max',
            # Campos de concesión / comisión
            'en_concesion', 'comision_por_kilo', 'fecha_limite_concesion'
        )
        extra_kwargs = {
            'numero_pallet': {'required': False, 'allow_null': True, 'allow_blank': True}
        }

class SupplierRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        from .models import Supplier
        import uuid
        try:
            uuid_obj = uuid.UUID(str(data))
            return Supplier.objects.get(uid=uuid_obj)
        except (ValueError, Supplier.DoesNotExist):
            return super().to_internal_value(data)

class GoodsReceptionListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listas de recepciones"""
    proveedor_nombre = serializers.SerializerMethodField()
    recibido_por_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = GoodsReception
        fields = (
            'uid', 'numero_guia', 'fecha_recepcion', 'proveedor_nombre', 'numero_guia_proveedor',
            'recibido_por_nombre', 'total_pallets', 'total_cajas', 'estado', 'estado_pago'
        )
    
    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if obj.proveedor else None
        
    def get_recibido_por_nombre(self, obj):
        if obj.recibido_por:
            return f"{obj.recibido_por.first_name} {obj.recibido_por.last_name}".strip()
        return None

class GoodsReceptionSerializer(serializers.ModelSerializer):
    proveedor = SupplierRelatedField(queryset=Supplier.objects.all())
    detalles = serializers.SerializerMethodField()
    detalles_data = ReceptionDetailSerializer(source='detalles', many=True, required=False, write_only=True)
    recibido_por_nombre = serializers.SerializerMethodField()
    revisado_por_nombre = serializers.SerializerMethodField()
    # Información básica del proveedor
    proveedor_info = serializers.SerializerMethodField()
    # Nuevos campos para comisión flexible (sin migraciones)
    # Los exponemos también en respuesta para que el frontend vea exactamente lo que envió
    comision_base = serializers.CharField(required=False, allow_blank=True)  # 'kg'|'caja'|'unidad'|'venta' (eco)
    comision_monto = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    comision_porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            ctx = getattr(self, 'context', {}) or {}
            commission_ctx = ctx.get('commission_input')
            if commission_ctx:
                # Permite que get_detalles y to_representation echen mano de los valores enviados
                self._commission_input = commission_ctx
        except Exception:
            pass

    def get_detalles(self, obj):
        """Retorna detalles completos necesarios para editar/actualizar en frontend (sin cálculos automáticos)."""
        detalles = []
        for d in obj.detalles.all():
            detalles.append({
                # Identificación
                'uid': d.uid,
                # Producto y BoxType (uids y nombres para selects)
                'producto': d.producto.uid if d.producto else None,
                'producto_nombre': d.producto.nombre if d.producto else None,
                'box_type': d.box_type.uid if getattr(d, 'box_type', None) else None,
                'box_type_nombre': d.box_type.nombre if getattr(d, 'box_type', None) else None,
                # Atributos de calidad y clasificación
                'variedad': d.variedad,
                'calibre': d.calibre,
                'calidad': d.calidad,
                'calidad_display': d.get_calidad_display(),
                'temperatura': d.temperatura,
                'estado_maduracion': d.estado_maduracion,
                # Cantidades y pesos
                'cantidad_cajas': d.cantidad_cajas,
                'peso_bruto': d.peso_bruto,
                'peso_tara': getattr(d, 'peso_tara', 0),
                # Costos y pérdidas
                'costo': d.costo,
                'porcentaje_perdida_estimado': d.porcentaje_perdida_estimado,
                'precio_sugerido_min': d.precio_sugerido_min,
                'precio_sugerido_max': d.precio_sugerido_max,
                # Concesión persistida en el detalle
                'en_concesion': getattr(d, 'en_concesion', getattr(obj, 'en_concesion', False)),
                'comision_por_kilo': getattr(d, 'comision_por_kilo', getattr(obj, 'comision_por_kilo', 0)),
                'fecha_limite_concesion': getattr(d, 'fecha_limite_concesion', getattr(obj, 'fecha_limite_concesion', None)),
                # Eco de campos de comisión a nivel recepción, para facilitar UI (sin cálculo)
                'comision_base': getattr(obj, 'comision_base', None),
                'comision_monto': float(getattr(obj, 'comision_monto', 0)) if getattr(obj, 'comision_monto', None) is not None else None,
                'comision_porcentaje': float(getattr(obj, 'comision_porcentaje', 0)) if getattr(obj, 'comision_porcentaje', None) is not None else None,
                # Referencia a lote creado (si existiese)
                'lote_id': d.lote_creado.id if getattr(d, 'lote_creado', None) else None,
            })
        return detalles
        
    def get_proveedor_info(self, obj):
        """Retorna información básica del proveedor"""
        if obj.proveedor:
            return {
                'uid': obj.proveedor.uid,
                'nombre': obj.proveedor.nombre,
                'rut': obj.proveedor.rut,
                'telefono': obj.proveedor.telefono,
                'email': obj.proveedor.email
            }
        return None
    
    def to_internal_value(self, data):
        import json
        detalles = data.get('detalles')
        if isinstance(detalles, str):
            try:
                data['detalles'] = json.loads(detalles)
            except Exception:
                raise serializers.ValidationError({'detalles': 'Debe ser un JSON válido.'})

        # Mapear 'detalles' de entrada al campo escribible 'detalles_data'
        if 'detalles' in data and 'detalles_data' not in data:
            data['detalles_data'] = data.get('detalles')

        # Convertir strings vacíos a None en campos de fecha
        fecha_limite = data.get('fecha_limite_concesion')
        if fecha_limite == '':
            data['fecha_limite_concesion'] = None
            
        fecha_recepcion = data.get('fecha_recepcion')
        if fecha_recepcion == '':
            data['fecha_recepcion'] = None
        
        # Capturar comisión virtual de entrada para eco en respuesta
        self._commission_input = {
            'comision_base': data.get('comision_base'),
            'comision_monto': data.get('comision_monto'),
            'comision_porcentaje': data.get('comision_porcentaje'),
        }
            
        return super().to_internal_value(data)

    class Meta:
        model = GoodsReception
        fields = (
            'uid', 'numero_guia', 'fecha_recepcion', 'proveedor', 'proveedor_info', 'numero_guia_proveedor', 'recibido_por',
            'revisado_por', 'recibido_por_nombre', 'revisado_por_nombre', 'estado', 'observaciones', 'estado_pago', 
            'total_pallets', 'total_cajas', 'total_peso_bruto', 'business', 'detalles', 'detalles_data',
            'en_concesion', 'comision_por_kilo', 'comision_base', 'comision_monto', 'comision_porcentaje', 'fecha_limite_concesion',
        )
        # Excluir IDs que no se utilizan de la respuesta (solo para escritura)
        extra_kwargs = {
            'proveedor': {'write_only': True},
            'recibido_por': {'write_only': True},
            'business': {'write_only': True}
        }
        
    def get_recibido_por_nombre(self, obj):
        if obj.recibido_por:
            return f"{obj.recibido_por.first_name} {obj.recibido_por.last_name}".strip()
        return None
        
    def get_revisado_por_nombre(self, obj):
        if obj.revisado_por:
            return f"{obj.revisado_por.first_name} {obj.revisado_por.last_name}".strip()
        return None

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles_data', [])
        
        # Extraer campos de concesión de la recepción
        en_concesion = validated_data.get('en_concesion', False)
        comision_por_kilo = validated_data.get('comision_por_kilo', 0)
        fecha_limite_concesion = validated_data.get('fecha_limite_concesion', None)

        # Sin cálculos automáticos: se persisten los campos tal como vienen

        recepcion = GoodsReception.objects.create(**validated_data)
        
        for detalle_data in detalles_data:
            # Propagar flags de concesión si no vienen en el detalle (pero sin calcular nada)
            detalle_data.setdefault('en_concesion', en_concesion)
            detalle_data.setdefault('comision_por_kilo', comision_por_kilo)
            detalle_data.setdefault('fecha_limite_concesion', fecha_limite_concesion)
        
            # detalle_data ya viene validado por ReceptionDetailSerializer, con FKs resueltos
            ReceptionDetail.objects.create(recepcion=recepcion, **detalle_data)
        return recepcion

    def update(self, instance, validated_data):
        # Usar la versión validada del nested serializer
        detalles_data = validated_data.pop('detalles_data', None)
        
        # Extraer campos de concesión de la recepción
        en_concesion = validated_data.get('en_concesion', instance.en_concesion)
        comision_por_kilo = validated_data.get('comision_por_kilo', instance.comision_por_kilo)
        fecha_limite_concesion = validated_data.get('fecha_limite_concesion', instance.fecha_limite_concesion)

        # Sin cálculos automáticos: se persisten los campos tal como vienen

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Si se enviaron detalles, reemplazar por completo
        if detalles_data is not None:
            # Elimina los detalles anteriores y crea los nuevos
            instance.detalles.all().delete()
            for detalle_data in detalles_data:
                # Agregar campos de concesión a cada detalle
                detalle_data['en_concesion'] = en_concesion
                detalle_data['comision_por_kilo'] = comision_por_kilo
                detalle_data['fecha_limite_concesion'] = fecha_limite_concesion
                
                # detalle_data ya viene validado por ReceptionDetailSerializer, con FKs resueltos
                ReceptionDetail.objects.create(recepcion=instance, **detalle_data)
        return instance

    def to_representation(self, instance):
        """Respuesta directa de los campos del modelo, sin inferencias automáticas."""
        return super().to_representation(instance)

class SupplierPaymentSerializer(serializers.ModelSerializer):
    metodo_pago_display = serializers.CharField(source='get_metodo_pago_display', read_only=True)
    recepcion_numero = serializers.SerializerMethodField()
    proveedor_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = SupplierPayment
        fields = [
            'uid', 'recepcion', 'recepcion_numero', 'monto', 'fecha_pago',
            'metodo_pago', 'metodo_pago_display', 'comprobante', 'notas',
            'proveedor_nombre', 'created_at', 'updated_at'
        ]
    
    def get_recepcion_numero(self, obj):
        return obj.recepcion.numero_guia if obj.recepcion else None
    
    def get_proveedor_nombre(self, obj):
        return obj.recepcion.proveedor.nombre if obj.recepcion and obj.recepcion.proveedor else None

class ConcessionSettlementDetailSerializer(serializers.ModelSerializer):
    lote_nombre = serializers.SerializerMethodField()
    venta_codigo = serializers.SerializerMethodField()
    
    class Meta:
        model = ConcessionSettlementDetail
        fields = [
            'id', 'liquidacion', 'venta', 'venta_codigo', 'item_venta', 'lote', 'lote_nombre',
            'cantidad_kilos', 'precio_venta', 'comision', 'monto_liquidado'
        ]
    
    def get_lote_nombre(self, obj):
        if obj.lote and obj.lote.producto:
            return f"{obj.lote.producto.nombre} - {obj.lote.calibre}"
        return f"Lote {obj.lote.id}" if obj.lote else None
    
    def get_venta_codigo(self, obj):
        return obj.venta.codigo_venta if obj.venta else None

class ConcessionSettlementSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.SerializerMethodField()
    proveedor_rut = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    detalles = ConcessionSettlementDetailSerializer(many=True, read_only=True)
    
    class Meta:
        model = ConcessionSettlement
        fields = [
            'uid', 'proveedor', 'proveedor_nombre', 'proveedor_rut', 'fecha_liquidacion',
            'total_kilos_vendidos', 'total_ventas', 'total_comision', 'monto_a_liquidar',
            'estado', 'estado_display', 'comprobante', 'notas', 'detalles',
            'created_at', 'updated_at'
        ]
    
    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if obj.proveedor else None
    
    def get_proveedor_rut(self, obj):
        return obj.proveedor.rut if obj.proveedor else None

class PalletHistorySerializerList(serializers.ModelSerializer):
    """Serializador para listar el historial de pallets vendidos o agotados"""
    nombre_producto = serializers.SerializerMethodField()
    calibre = serializers.CharField(read_only=True)
    proveedor = serializers.CharField(read_only=True)
    procedencia = serializers.CharField(read_only=True)
    fecha_ingreso = serializers.DateField(read_only=True)
    fecha_ultima_venta = serializers.SerializerMethodField()
    total_generado = serializers.SerializerMethodField()
    
    class Meta:
        model = FruitLot
        fields = (
            'uid', 'nombre_producto', 'calibre', 'proveedor', 'procedencia',
            'fecha_ingreso', 'fecha_ultima_venta', 'total_generado'
        )
    
    def get_nombre_producto(self, obj):
        return obj.producto.nombre if obj.producto else 'Desconocido'
    
    def get_fecha_ultima_venta(self, obj):
        # Obtener la fecha de la última venta relacionada con este lote
        ultima_venta = SaleItem.objects.filter(
            lote=obj
        ).aggregate(ultima_fecha=Max('created_at'))
        
        return ultima_venta.get('ultima_fecha')
    
    def get_total_generado(self, obj):
        # Calcular el total generado por las ventas de este lote
        ventas = SaleItem.objects.filter(lote=obj)
        
        # Sumar todos los subtotales de los items de venta
        total = ventas.aggregate(total=Sum('subtotal'))['total'] or 0
        
        return total

class PalletHistoryDetailSerializer(serializers.ModelSerializer):
    """Serializador para el detalle de un pallet vendido o agotado, específico por tipo de fruta"""
    nombre_producto = serializers.SerializerMethodField()
    tipo_producto = serializers.SerializerMethodField()
    calibre = serializers.CharField(read_only=True)
    proveedor = serializers.CharField(read_only=True)
    procedencia = serializers.CharField(read_only=True)
    pais = serializers.CharField(read_only=True)
    fecha_ingreso = serializers.DateField(read_only=True)
    fecha_ultima_venta = serializers.SerializerMethodField()
    total_generado = serializers.SerializerMethodField()
    costo_total_pallet = serializers.SerializerMethodField()
    ganancia_pallet = serializers.SerializerMethodField()
    margen_ganancia = serializers.SerializerMethodField()
    resumen_ventas = serializers.SerializerMethodField()
    ventas_detalle = serializers.SerializerMethodField()
    # Campos específicos por tipo de producto
    datos_especificos = serializers.SerializerMethodField()
    
    class Meta:
        model = FruitLot
        fields = (
            'uid', 'nombre_producto', 'tipo_producto', 'calibre', 'proveedor', 
            'procedencia', 'pais', 'fecha_ingreso', 'fecha_ultima_venta', 
            'total_generado', 'costo_total_pallet', 'ganancia_pallet', 'margen_ganancia',
            'resumen_ventas', 'ventas_detalle', 'datos_especificos'
        )
    
    def get_nombre_producto(self, obj):
        return obj.producto.nombre if obj.producto else 'Desconocido'
    
    def get_tipo_producto(self, obj):
        return obj.producto.tipo_producto if obj.producto else 'desconocido'
    
    def get_fecha_ultima_venta(self, obj):
        # Obtener la fecha de la última venta relacionada con este lote
        ultima_venta = SaleItem.objects.filter(
            lote=obj
        ).aggregate(ultima_fecha=Max('created_at'))
        
        return ultima_venta.get('ultima_fecha')
    
    def get_total_generado(self, obj):
        # Calcular el total generado por las ventas de este lote
        ventas = SaleItem.objects.filter(lote=obj)
        
        # Sumar todos los subtotales de los items de venta
        total = ventas.aggregate(total=Sum('subtotal'))['total'] or 0
        
        # Convertir a float para evitar problemas de tipo
        return float(total)
    
    def get_ventas_detalle(self, obj):
        # Obtener todas las ventas relacionadas con este lote
        ventas = SaleItem.objects.filter(lote=obj).select_related('venta')
        
        # Crear un resumen de cada venta
        resultado = []
        for venta in ventas:
            item = {
                'fecha_venta': venta.created_at,
                'codigo_venta': venta.venta.codigo_venta if hasattr(venta, 'venta') and venta.venta else 'N/A',
                'subtotal': float(venta.subtotal) if venta.subtotal else 0,
                'cliente': venta.venta.cliente.nombre if hasattr(venta, 'venta') and venta.venta and venta.venta.cliente else 'Cliente no registrado',
            }
            
            # Añadir campos específicos según el tipo de producto
            if obj.producto and obj.producto.tipo_producto == 'palta':
                item['peso_vendido'] = float(venta.peso_vendido) if venta.peso_vendido else 0
                item['precio_kg'] = float(venta.precio_kg) if venta.precio_kg else 0
                
                # Calcular costo_kg con conversión segura a float
                costo_kg = 0
                if hasattr(venta, 'costo_kg') and venta.costo_kg:
                    costo_kg = float(venta.costo_kg)
                elif obj.costo_inicial:
                    costo_kg = float(obj.costo_inicial)
                item['costo_kg'] = costo_kg
                
                # Calcular ganancia con valores ya convertidos
                precio_kg = item['precio_kg']
                item['ganancia_kg'] = precio_kg - costo_kg
                item['ganancia_item'] = item['ganancia_kg'] * item['peso_vendido']
            else:  # tipo 'otro'
                item['unidades_vendidas'] = int(venta.unidades_vendidas) if venta.unidades_vendidas else 0
                item['precio_unidad'] = float(venta.precio_unidad) if venta.precio_unidad else 0
                
                # Calcular costo_unidad con conversión segura a float
                costo_unidad = 0
                if hasattr(venta, 'costo_unidad') and venta.costo_unidad:
                    costo_unidad = float(venta.costo_unidad)
                elif obj.costo_inicial:
                    costo_unidad = float(obj.costo_inicial)
                item['costo_unidad'] = costo_unidad
                
                # Calcular ganancia con valores ya convertidos
                precio_unidad = item['precio_unidad']
                item['ganancia_unidad'] = precio_unidad - costo_unidad
                item['ganancia_item'] = item['ganancia_unidad'] * item['unidades_vendidas']
                
            resultado.append(item)
            
        return resultado
    
    def get_datos_especificos(self, obj):
        """Devuelve datos específicos según el tipo de producto"""
        if not obj.producto:
            return {}
            
        if obj.producto.tipo_producto == 'palta':
            # Datos específicos para paltas
            return {
                'peso_bruto': float(obj.peso_bruto) if obj.peso_bruto else 0,
                'peso_neto': float(obj.peso_neto) if obj.peso_neto else 0,
                'cantidad_cajas': obj.cantidad_cajas,
                'box_type': obj.box_type.nombre if obj.box_type else 'N/A',
                'pallet_type': obj.pallet_type.nombre if obj.pallet_type else 'N/A',
                'estado_maduracion': obj.estado_maduracion,
                'costo_inicial': float(obj.costo_inicial) if obj.costo_inicial else 0,
                'costo_kg': float(obj.costo_inicial) if obj.costo_inicial else 0,
                'precio_sugerido_min': float(obj.precio_sugerido_min) if obj.precio_sugerido_min else 0,
                'precio_sugerido_max': float(obj.precio_sugerido_max) if obj.precio_sugerido_max else 0,
                'peso_vendido_total': self.get_peso_vendido(obj),
            }
        else:  # tipo 'otro'
            # Datos específicos para otros productos
            return {
                'cantidad_unidades': obj.cantidad_unidades,
                'unidades_por_caja': obj.unidades_por_caja,
                'cantidad_cajas': obj.cantidad_cajas,
                'box_type': obj.box_type.nombre if obj.box_type else 'N/A',
                'costo_inicial': float(obj.costo_inicial) if obj.costo_inicial else 0,
                'costo_unidad': float(obj.costo_inicial) / obj.unidades_por_caja if obj.costo_inicial and obj.unidades_por_caja else 0,
                'precio_sugerido_min': float(obj.precio_sugerido_min) if obj.precio_sugerido_min else 0,
                'precio_sugerido_max': float(obj.precio_sugerido_max) if obj.precio_sugerido_max else 0,
                'unidades_vendidas_total': self.get_unidades_vendidas(obj),
            }
            
    def get_ganancia_pallet(self, obj):
        """Calcula la ganancia total del pallet (total generado - costo de lo vendido)"""
        # Convertir todos los valores a float para evitar problemas de tipo
        total_generado = float(self.get_total_generado(obj))
        
        # Calculamos el costo solo de lo que se ha vendido, no del pallet completo
        if obj.producto and obj.producto.tipo_producto == 'palta':
            peso_vendido = self.get_peso_vendido(obj)
            costo_por_kg = float(obj.costo_inicial or 0)
            costo_vendido = round(peso_vendido * costo_por_kg, 2)
        else:  # tipo 'otro'
            unidades_vendidas = self.get_unidades_vendidas(obj)
            costo_por_unidad = float(obj.costo_inicial or 0) / max(1, obj.unidades_por_caja)
            costo_vendido = round(unidades_vendidas * costo_por_unidad, 2)
            
        return total_generado - costo_vendido
    
    def get_margen_ganancia(self, obj):
        """Calcula el margen de ganancia como porcentaje"""
        # Calculamos el costo solo de lo que se ha vendido, no del pallet completo
        if obj.producto and obj.producto.tipo_producto == 'palta':
            peso_vendido = self.get_peso_vendido(obj)
            costo_por_kg = float(obj.costo_inicial or 0)
            costo_vendido = round(peso_vendido * costo_por_kg, 2)
        else:  # tipo 'otro'
            unidades_vendidas = self.get_unidades_vendidas(obj)
            costo_por_unidad = float(obj.costo_inicial or 0) / max(1, obj.unidades_por_caja)
            costo_vendido = round(unidades_vendidas * costo_por_unidad, 2)
        
        ganancia = self.get_ganancia_pallet(obj)
        
        if costo_vendido > 0:
            return round((ganancia / costo_vendido) * 100, 2)
        elif ganancia > 0:
            # Si hay ganancia pero no hay costo registrado, el margen es técnicamente infinito
            # pero reportamos 100% como valor máximo
            return 100.0
        return 0.0
    
    def get_peso_vendido(self, obj):
        """Calcula el peso total vendido para paltas"""
        if not obj.producto or obj.producto.tipo_producto != 'palta':
            return 0
            
        ventas = SaleItem.objects.filter(lote=obj)
        return float(ventas.aggregate(total=Sum('peso_vendido'))['total'] or 0)
    
    def get_unidades_vendidas(self, obj):
        """Calcula las unidades totales vendidas para otros productos"""
        if not obj.producto or obj.producto.tipo_producto == 'palta':
            return 0
            
        ventas = SaleItem.objects.filter(lote=obj)
        return ventas.aggregate(total=Sum('unidades_vendidas'))['total'] or 0
        
    def get_costo_total_pallet(self, obj):
        """Calcula el costo total del pallet según su tipo, usando el peso histórico"""
        if not obj.producto:
            return 0.0
            
        try:
            # Obtener el resumen de ventas que ya tiene calculado el costo vendido
            resumen = self.get_resumen_ventas(obj)
            if resumen and 'costo_vendido' in resumen:
                return float(resumen['costo_vendido'])
                
            # Si no podemos obtener el costo desde el resumen, calcularlo manualmente
            if obj.producto.tipo_producto == 'palta':
                # Para paltas, usamos el peso vendido total del campo datos_especificos
                datos_especificos = self.get_datos_especificos(obj)
                if datos_especificos and 'peso_vendido_total' in datos_especificos:
                    peso_vendido_total = float(datos_especificos['peso_vendido_total'])
                    costo_inicial = float(obj.costo_inicial or 0)
                    return round(peso_vendido_total * costo_inicial, 2)
                
                # Si no está en datos_especificos, calcularlo desde las ventas
                from django.db.models import Sum
                ventas = SaleItem.objects.filter(lote=obj)
                peso_vendido_total = ventas.aggregate(total=Sum('peso_vendido'))['total'] or 0
                costo_inicial = float(obj.costo_inicial or 0)
                
                # Si no hay ventas registradas, usamos el peso bruto menos la tara estimada
                if peso_vendido_total == 0:
                    # Estimamos el peso neto original basado en el peso bruto
                    peso_bruto = float(obj.peso_bruto or 0)
                    tara_estimada = 0
                    if obj.box_type:
                        tara_estimada += float(obj.box_type.peso_caja or 0) * float(obj.cantidad_cajas or 1)
                    if obj.pallet_type:
                        tara_estimada += float(obj.pallet_type.peso_pallet or 0)
                    peso_vendido_total = max(0, peso_bruto - tara_estimada)
                
                return round(peso_vendido_total * costo_inicial, 2)
            else:  # tipo 'otro'
                # Para otros productos, el costo es por cantidad de unidades históricas
                from django.db.models import Sum
                ventas = SaleItem.objects.filter(lote=obj)
                unidades_vendidas_total = ventas.aggregate(total=Sum('unidades_vendidas'))['total'] or 0
                
                # Si no hay ventas registradas, usamos la cantidad de unidades original
                if unidades_vendidas_total == 0:
                    unidades_vendidas_total = float(obj.cantidad_unidades or 0)
                
                costo_por_unidad = float(obj.costo_inicial or 0) / max(1, obj.unidades_por_caja or 1)
                return round(unidades_vendidas_total * costo_por_unidad, 2)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculando costo total del pallet: {str(e)}")
            # En caso de error, devolver el costo vendido del resumen si está disponible
            try:
                resumen = self.get_resumen_ventas(obj)
                if resumen and 'costo_vendido' in resumen:
                    return float(resumen['costo_vendido'])
            except Exception:
                pass
            return 0.0
    
    def get_resumen_ventas(self, obj):
        """Proporciona un resumen de las ventas del pallet"""
        ventas = SaleItem.objects.filter(lote=obj)
        num_ventas = ventas.count()
        
        if not obj.producto:
            return {
                'num_ventas': num_ventas,
                'total_generado': float(self.get_total_generado(obj))
            }
        
        total_generado = float(self.get_total_generado(obj))
        
        # Calculamos el costo solo de lo que se ha vendido, no del pallet completo
        if obj.producto.tipo_producto == 'palta':
            # Para paltas
            peso_total_vendido = self.get_peso_vendido(obj)
            costo_por_kg = float(obj.costo_inicial or 0)
            costo_vendido = round(peso_total_vendido * costo_por_kg, 2)
            
            precio_promedio_kg = 0
            if peso_total_vendido > 0:
                precio_promedio_kg = round(total_generado / peso_total_vendido, 2)
            
            ganancia_total = total_generado - costo_vendido
            
            # Calcular margen de ganancia sobre lo vendido
            margen_ganancia = 0
            if costo_vendido > 0:
                margen_ganancia = round((ganancia_total / costo_vendido) * 100, 2)
            elif ganancia_total > 0:
                # Si hay ganancia pero no hay costo registrado, reportamos 100%
                margen_ganancia = 100.0
                
            return {
                'num_ventas': num_ventas,
                'peso_total_vendido': peso_total_vendido,
                'precio_promedio_kg': precio_promedio_kg,
                'total_generado': total_generado,
                'costo_vendido': costo_vendido,
                'ganancia_total': ganancia_total,
                'margen_ganancia': margen_ganancia
            }
        else:  # tipo 'otro'
            # Para otros productos
            unidades_total_vendidas = self.get_unidades_vendidas(obj)
            costo_por_unidad = float(obj.costo_inicial or 0) / max(1, obj.unidades_por_caja)
            costo_vendido = round(unidades_total_vendidas * costo_por_unidad, 2)
            
            precio_promedio_unidad = 0
            if unidades_total_vendidas > 0:
                precio_promedio_unidad = round(total_generado / unidades_total_vendidas, 2)
            
            ganancia_total = total_generado - costo_vendido
            
            # Calcular margen de ganancia sobre lo vendido
            margen_ganancia = 0
            if costo_vendido > 0:
                margen_ganancia = round((ganancia_total / costo_vendido) * 100, 2)
            elif ganancia_total > 0:
                # Si hay ganancia pero no hay costo registrado, reportamos 100%
                margen_ganancia = 100.0
                
            return {
                'num_ventas': num_ventas,
                'unidades_total_vendidas': unidades_total_vendidas,
                'precio_promedio_unidad': precio_promedio_unidad,
                'total_generado': total_generado,
                'costo_vendido': costo_vendido,
                'ganancia_total': ganancia_total,
                'margen_ganancia': margen_ganancia
            }
