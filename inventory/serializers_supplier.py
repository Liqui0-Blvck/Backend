from rest_framework import serializers
from .models import Supplier, SupplierPayment, GoodsReception, ReceptionDetail, ConcessionSettlement, ConcessionSettlementDetail
from django.db.models import Sum, Max, Count


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
    
    class Meta:
        model = Supplier
        fields = (
            'uid', 'nombre', 'rut', 'telefono', 'email', 'contacto', 
            'activo', 'total_deuda', 'total_pagado', 'recepciones_count',
            'liquidaciones_count', 'ultima_actividad'
        )
    
    def get_total_deuda(self, obj):
        """Calcula la deuda total pendiente del proveedor"""
        # Calcular el total de deuda sumando los montos totales de todas las recepciones
        total = obj.recepciones.aggregate(total=Sum('monto_total'))['total'] or 0
        
        # Restar los pagos realizados
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj)
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
    
    class Meta:
        model = Supplier
        fields = ('uid', 'nombre', 'rut', 'direccion', 'telefono', 'email', 'contacto', 'observaciones', 
                 'business', 'activo', 'created_at', 'updated_at',
                 'total_deuda', 'total_pagado', 'recepciones_pendientes',
                 'cantidad_recepciones', 'cantidad_liquidaciones', 'cantidad_pallets', 'cantidad_cajas',
                 'total_kg_recepcionados', 'ultima_recepcion', 'ultima_liquidacion', 'ultimo_pago',
                 'detalle_pallets', 'resumen_pagos', 'resumen_liquidaciones')
    
    def get_total_deuda(self, obj):
        """Calcula la deuda total pendiente del proveedor"""
        # Calcular el total de deuda sumando los montos totales de todas las recepciones
        total = obj.recepciones.aggregate(total=Sum('monto_total'))['total'] or 0
        
        # Restar los pagos realizados
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj)
        total_pagado = pagos.aggregate(total=Sum('monto'))['total'] or 0
        
        return total - total_pagado
    
    def get_total_pagado(self, obj):
        """Suma todos los pagos realizados al proveedor"""
        pagos = SupplierPayment.objects.filter(recepcion__proveedor=obj)
        return pagos.aggregate(total=Sum('monto'))['total'] or 0
    
    def get_recepciones_pendientes(self, obj):
        """Retorna las recepciones pendientes de pago"""
        # Obtener todas las recepciones del proveedor
        recepciones = obj.recepciones.all()
        
        # Lista para almacenar las recepciones pendientes
        pendientes = []
        
        for recepcion in recepciones:
            # Calcular el monto total de la recepción
            monto_total = recepcion.monto_total or 0
            
            # Calcular el total pagado para esta recepción
            pagos = recepcion.pagos.aggregate(total=Sum('monto'))['total'] or 0
            
            # Si hay saldo pendiente, agregar a la lista
            if monto_total > pagos:
                pendientes.append({
                    'uid': recepcion.uid,
                    'numero_guia': recepcion.numero_guia,
                    'fecha_recepcion': recepcion.fecha_recepcion,
                    'monto_total': monto_total,
                    'monto_pagado': pagos,
                    'saldo_pendiente': monto_total - pagos
                })
        
        return pendientes
    
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
                    'peso_neto': detalle.peso_neto,
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
