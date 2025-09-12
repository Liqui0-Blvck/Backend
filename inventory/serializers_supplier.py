from rest_framework import serializers
from .models import Supplier, SupplierPayment, GoodsReception, ReceptionDetail, ConcessionSettlement, ConcessionSettlementDetail, FruitBin
from .fruit_bin_serializers import FruitBinListSerializer
from .bin_to_lot_models import BinToLotTransformationDetail
from django.db.models import Sum, Max, Count
from accounts.models import Perfil
from sales.models import SaleItem


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
    # Pallets originados desde bins del proveedor
    detalle_pallets_desde_bins = serializers.SerializerMethodField()
    
    # Campos para análisis financiero
    resumen_pagos = serializers.SerializerMethodField()
    resumen_liquidaciones = serializers.SerializerMethodField()
    vinculado = serializers.SerializerMethodField()
    # Bins del proveedor
    detalle_bins = serializers.SerializerMethodField()

    # Nuevos KPIs de ventas
    ventas_por_recepcion = serializers.SerializerMethodField()
    ventas_totales = serializers.SerializerMethodField()
    ventas_desde_transformados = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = ('uid', 'nombre', 'rut', 'direccion', 'telefono', 'email', 'contacto', 'observaciones', 
                 'business', 'activo', 'created_at', 'updated_at',
                 'total_deuda', 'total_pagado', 'recepciones_pendientes',
                 'cantidad_recepciones', 'cantidad_liquidaciones', 'cantidad_pallets', 'cantidad_cajas',
                 'total_kg_recepcionados', 'ultima_recepcion', 'ultima_liquidacion', 'ultimo_pago',
                 'detalle_pallets', 'detalle_pallets_desde_bins', 'detalle_bins', 'resumen_pagos', 'resumen_liquidaciones', 'vinculado',
                 'ventas_por_recepcion', 'ventas_totales', 'ventas_desde_transformados')
    
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
    
    def get_recepciones_pendientes(self, obj):
        """Retorna las últimas 5 recepciones del proveedor con su estado"""
        # Obtener recepciones del proveedor excluyendo rechazadas, ordenadas por fecha (más recientes primero)
        recepciones = obj.recepciones.exclude(estado='rechazado').order_by('-fecha_recepcion')[:5]
        
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
        # Obtener recepciones del proveedor excluyendo rechazadas
        recepciones = obj.recepciones.exclude(estado='rechazado')
        
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
                    'precio_compra': detalle.costo,
                })
        
        return detalles

    def get_detalle_pallets_desde_bins(self, obj):
        """Retorna pallets (FruitLot) que se originaron desde bins pertenecientes a este proveedor.
        Usa la trazabilidad BinToLotTransformationDetail -> Bin (proveedor) -> Transformación -> Lote.
        """
        try:
            # Encontrar todos los lotes vinculados a transformaciones cuyos bins pertenecen a este proveedor
            detalles = (
                BinToLotTransformationDetail.objects
                .select_related('transformacion', 'transformacion__lote', 'bin', 'bin__producto')
                .filter(bin__proveedor=obj)
                .order_by('-transformacion__fecha_transformacion')
            )
            resultado = []
            vistos = set()
            for d in detalles:
                lote = getattr(d.transformacion, 'lote', None)
                if not lote or lote.pk in vistos:
                    continue
                vistos.add(lote.pk)
                resultado.append({
                    'lote_uid': str(getattr(lote, 'uid', None)),
                    'producto': getattr(getattr(lote, 'producto', None), 'nombre', 'No especificado'),
                    'calibre': getattr(lote, 'calibre', None),
                    'cantidad_cajas': getattr(lote, 'cantidad_cajas', None),
                    'peso_bruto': getattr(lote, 'peso_bruto', None),
                    'peso_neto': getattr(lote, 'peso_neto', None),
                    'fecha_ingreso': getattr(lote, 'fecha_ingreso', None),
                    'codigo': getattr(lote, 'qr_code', None),
                    'origen': 'bin',
                })
            return resultado
        except Exception:
            return []

    def get_detalle_bins(self, obj):
        """Retorna bins pertenecientes al proveedor (excluye bins cuya recepción esté rechazada)."""
        try:
            qs = FruitBin.objects.filter(proveedor=obj)
            # Excluir bins asociados a una recepción rechazada
            qs = qs.exclude(recepcion__estado='rechazado')
            serializer = FruitBinListSerializer(qs, many=True)
            return serializer.data
        except Exception:
            return []

    def _aggregate_ventas_qs(self, saleitems_qs):
        """Helper: agrega métricas de ventas para un queryset de SaleItem."""
        total_monto = saleitems_qs.aggregate(total=Sum('subtotal'))['total'] or 0
        total_kg = saleitems_qs.aggregate(total=Sum('peso_vendido'))['total'] or 0
        total_cajas = saleitems_qs.aggregate(total=Sum('unidades_vendidas'))['total'] or 0
        ventas_count = saleitems_qs.values('venta').distinct().count()
        return {
            'ventas': int(ventas_count),
            'kg_vendidos': float(total_kg or 0),
            'cajas_vendidas': int(total_cajas or 0),
            'monto_total': float(total_monto or 0),
        }

    def get_ventas_por_recepcion(self, obj):
        """Ventas de productos del proveedor separadas por cada recepción y con detalle por lote."""
        resultados = []
        recepciones = obj.recepciones.exclude(estado='rechazado').order_by('-fecha_recepcion')
        for recepcion in recepciones:
            lot_ids = list(
                recepcion.detalles.exclude(lote_creado__isnull=True).values_list('lote_creado_id', flat=True)
            )
            if not lot_ids:
                resultados.append({
                    'recepcion_uid': recepcion.uid,
                    'numero_guia': recepcion.numero_guia,
                    'fecha_recepcion': recepcion.fecha_recepcion,
                    'resumen': {'ventas': 0, 'kg_vendidos': 0.0, 'cajas_vendidas': 0, 'monto_total': 0.0},
                    'por_lote': []
                })
                continue
            items_qs = SaleItem.objects.filter(lote_id__in=lot_ids)
            resumen = self._aggregate_ventas_qs(items_qs)
            por_lote = []
            items_por_lote = items_qs.values('lote_id').annotate(
                monto=Sum('subtotal'),
                kg=Sum('peso_vendido'),
                cajas=Sum('unidades_vendidas'),
                ventas=Count('venta', distinct=True)
            )
            detalles_map = {d.lote_creado_id: d for d in recepcion.detalles.all() if getattr(d, 'lote_creado_id', None)}
            for row in items_por_lote:
                d = detalles_map.get(row['lote_id'])
                por_lote.append({
                    'lote_id': row['lote_id'],
                    'producto': getattr(getattr(d, 'producto', None), 'nombre', None) if d else None,
                    'calibre': getattr(d, 'calibre', None) if d else None,
                    'cantidad_cajas_recepcionadas': getattr(d, 'cantidad_cajas', None) if d else None,
                    'monto_total': float(row['monto'] or 0),
                    'kg_vendidos': float(row['kg'] or 0),
                    'cajas_vendidas': int(row['cajas'] or 0),
                    'ventas': int(row['ventas'] or 0),
                })
            resultados.append({
                'recepcion_uid': recepcion.uid,
                'numero_guia': recepcion.numero_guia,
                'fecha_recepcion': recepcion.fecha_recepcion,
                'resumen': resumen,
                'por_lote': por_lote,
            })
        return resultados

    def get_ventas_totales(self, obj):
        """Totales de ventas considerando todos los lotes recepcionados del proveedor."""
        lot_ids = []
        for r in obj.recepciones.exclude(estado='rechazado').all():
            lot_ids.extend(list(r.detalles.exclude(lote_creado__isnull=True).values_list('lote_creado_id', flat=True)))
        if not lot_ids:
            return {'ventas': 0, 'kg_vendidos': 0.0, 'cajas_vendidas': 0, 'monto_total': 0.0}
        items_qs = SaleItem.objects.filter(lote_id__in=lot_ids)
        return self._aggregate_ventas_qs(items_qs)

    def get_ventas_desde_transformados(self, obj):
        """Ventas de lotes que se originaron desde bins de este proveedor (post-transformación)."""
        detalles = (
            BinToLotTransformationDetail.objects
            .select_related('transformacion', 'transformacion__lote')
            .filter(bin__proveedor=obj)
        )
        lot_ids = []
        vistos = set()
        for d in detalles:
            lote = getattr(d.transformacion, 'lote', None)
            if not lote or lote.pk in vistos:
                continue
            vistos.add(lote.pk)
            lot_ids.append(lote.pk)
        if not lot_ids:
            return {'ventas': 0, 'kg_vendidos': 0.0, 'cajas_vendidas': 0, 'monto_total': 0.0}
        items_qs = SaleItem.objects.filter(lote_id__in=lot_ids)
        return self._aggregate_ventas_qs(items_qs)
    
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
