from rest_framework import serializers
from decimal import Decimal
import json
from django.db import models, transaction
from django.db.models import Sum
from .models import Sale, SalePending, SalePendingItem, Customer, CustomerPayment, SaleItem
from accounts.serializers import CustomUserSerializer
from inventory.models import FruitLot, StockReservation, Product, FruitBin, BoxType
from inventory.fruit_bin_serializers import FruitBinDetailSerializer
from .serializers_billing import BillingInfoNestedSerializer


class CustomerSerializer(serializers.ModelSerializer):
    credito_disponible = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    pagos_pendientes = serializers.IntegerField(read_only=True)
    ultimas_compras = serializers.SerializerMethodField(read_only=True)
    ultimos_pagos = serializers.SerializerMethodField(read_only=True)
    resumen_credito = serializers.SerializerMethodField(read_only=True)
    billing_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Customer
        fields = '__all__'
    
    def get_ultimas_compras(self, obj):
        # Obtener las últimas 5 compras del cliente
        ultimas_compras = obj.sales.all().order_by('-created_at')[:5]
        
        return [{
            'uid': venta.uid,
            'codigo_venta': venta.codigo_venta,
            'fecha': venta.created_at,
            'total': venta.total,
            'metodo_pago': venta.metodo_pago,
            'pagado': venta.pagado,
            'estado_pago': venta.estado_pago,
            'saldo_pendiente': venta.saldo_pendiente,
            'monto_pagado': venta.total - venta.saldo_pendiente,  # Monto ya pagado
            'porcentaje_pagado': round((1 - (venta.saldo_pendiente / venta.total)) * 100 if venta.total > 0 else 0, 2),  # Porcentaje pagado
            'producto': venta.items.first().lote.producto.nombre if venta.items.exists() and venta.items.first().lote and venta.items.first().lote.producto else None,
            'peso_vendido': venta.items.first().peso_vendido if venta.items.exists() else 0,
            'pagos_asociados': [{
                'uid': pago.uid,
                'fecha': pago.created_at,
                'monto': pago.monto,
                'metodo_pago': pago.metodo_pago
            } for pago in venta.pagos.all().order_by('-created_at')[:3]]  # Últimos 3 pagos asociados a esta venta
        } for venta in ultimas_compras]
    
    def get_ultimos_pagos(self, obj):
        # Obtener los últimos 5 pagos del cliente
        ultimos_pagos = obj.pagos.all().order_by('-created_at')[:5]
        
        return [{
            'uid': pago.uid,
            'fecha': pago.created_at,
            'monto': pago.monto,
            'metodo_pago': pago.metodo_pago,
            'referencia': pago.referencia,
            'ventas_asociadas': [{'uid': v.uid, 'codigo_venta': v.codigo_venta} for v in pago.ventas.all()]
        } for pago in ultimos_pagos]
    
    def get_resumen_credito(self, obj):
        # Calcular estadísticas de crédito
        total_compras = obj.sales.filter(metodo_pago='credito').count()
        total_pagos = obj.pagos.count()
        monto_total_compras = obj.sales.filter(metodo_pago='credito').aggregate(
            total=models.Sum('total')
        )['total'] or 0
        monto_total_pagos = obj.pagos.aggregate(
            total=models.Sum('monto')
        )['total'] or 0
        
        # Calcular ventas pendientes y parciales
        ventas_pendientes = obj.sales.filter(metodo_pago='credito', estado_pago='pendiente').count()
        ventas_parciales = obj.sales.filter(metodo_pago='credito', estado_pago='parcial').count()
        
        return {
            'total_compras_credito': total_compras,
            'total_pagos': total_pagos,
            'ventas_pendientes': ventas_pendientes,
            'ventas_parciales': ventas_parciales,
            'monto_total_compras': monto_total_compras,
            'monto_total_pagos': monto_total_pagos,
            'saldo_actual': obj.saldo_actual,
            'credito_disponible': obj.credito_disponible,
            'limite_credito': obj.limite_credito
        }
        
    def get_billing_info(self, obj):
        """Devuelve la información de facturación del cliente si existe"""
        try:
            if hasattr(obj, 'billing_info'):
                return BillingInfoNestedSerializer(obj.billing_info).data
        except Exception:
            pass
        return None


class CustomerPaymentSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.SerializerMethodField(read_only=True)
    orden_asociada = serializers.SerializerMethodField(read_only=True)

    
    class Meta:
        model = CustomerPayment
        fields = '__all__'
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return None

    def get_orden_asociada(self, obj):
        if obj.ventas.exists():
            return obj.ventas.first().codigo_venta
        return None
    
    # def get_ventas_info(self, obj):
    #     """Devuelve información resumida de las ventas asociadas a este pago"""
    #     return [{
    #         'uid': venta.uid,
    #         'codigo_venta': venta.codigo_venta,
    #         'total': venta.total,
    #         'saldo_pendiente': venta.saldo_pendiente,
    #         'estado_pago': venta.estado_pago,
    #         'fecha': venta.created_at,
    #         'orden_asociada': venta.codigo_venta
    #     } for venta in obj.ventas.all().order_by('created_at')]


class SalePendingItemSerializer(serializers.ModelSerializer):
    """Serializador para LEER los items de una venta pendiente."""
    producto_nombre = serializers.SerializerMethodField(read_only=True)
    calibre = serializers.SerializerMethodField(read_only=True)
    lote = serializers.CharField(source='lote.uid', read_only=True)
    bin = serializers.CharField(source='bin.uid', read_only=True)
    # Detalle completo del lote para que el frontend tenga toda la info de origen
    lote_detalle = serializers.SerializerMethodField(read_only=True)
    # Detalle básico del bin
    bin_detalle = serializers.SerializerMethodField(read_only=True)
    # Cantidades reservadas asociadas a este item pendiente
    cajas_reservadas = serializers.SerializerMethodField(read_only=True)
    kg_reservados = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SalePendingItem
        fields = [
            'uid', 'lote', 'bin', 'producto_nombre', 'calibre', 'lote_detalle', 'bin_detalle',
            'cantidad_unidades', 'precio_unidad',
            'cantidad_kg', 'precio_kg', 'subtotal',
            'cajas_reservadas', 'kg_reservados'
        ]

    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            return obj.vendedor.username
        return None

    def get_lote_detalle(self, obj):
        """Devuelve información detallada del lote de origen, similar a FruitLotSaleSerializer."""
        lote = getattr(obj, 'lote', None)
        if not lote:
            return None
        try:
            producto = getattr(lote, 'producto', None)
            return {
                'uid': getattr(lote, 'uid', None),
                'producto': {
                    'uid': getattr(producto, 'uid', None) if producto else None,
                    'nombre': getattr(producto, 'nombre', None) if producto else None,
                    'tipo_producto': getattr(producto, 'tipo_producto', None) if producto else None,
                    'marca': getattr(producto, 'marca', None) if producto else None,
                } if producto else None,
                'proveedor_nombre': getattr(getattr(lote, 'proveedor', None), 'name', None),
                'propietario_original_nombre': getattr(getattr(lote, 'propietario_original', None), 'name', None),
                'calibre': getattr(lote, 'calibre', None),
                'fecha_ingreso': getattr(lote, 'fecha_ingreso', None),
                'en_concesion': getattr(lote, 'en_concesion', None),
            }
        except Exception:
            return None

    def get_bin_detalle(self, obj):
        """Información básica del bin si el item es por bin."""
        bin_obj = getattr(obj, 'bin', None)
        if not bin_obj:
            return None
        try:
            # Usar el serializador detallado para exponer más campos del bin
            return FruitBinDetailSerializer(bin_obj).data
        except Exception:
            return None

    def get_producto_nombre(self, obj):
        try:
            if getattr(obj, 'lote', None) and getattr(obj.lote, 'producto', None):
                return obj.lote.producto.nombre
            if getattr(obj, 'bin', None) and getattr(obj.bin, 'producto', None):
                return obj.bin.producto.nombre
        except Exception:
            pass
        return None

    def get_calibre(self, obj):
        try:
            # Solo aplica a lotes; bins no tienen calibre
            if getattr(obj, 'lote', None):
                return getattr(obj.lote, 'calibre', None)
        except Exception:
            pass
        return None

    def get_cajas_reservadas(self, obj):
        """Total de cajas reservadas en estado en_proceso para este item pendiente."""
        try:
            from inventory.models import StockReservation
            agg = StockReservation.objects.filter(
                item_venta_pendiente=obj,
                estado='en_proceso'
            ).aggregate(total=models.Sum('cajas_reservadas'))
            return agg['total'] or 0
        except Exception:
            return 0

    def get_kg_reservados(self, obj):
        """Total de kg reservados en estado en_proceso para este item pendiente."""
        try:
            # Si el item es por bin o el producto no es palta, no aplica
            if getattr(obj, 'bin', None):
                return None
            lote = getattr(obj, 'lote', None)
            if not lote or not getattr(lote, 'producto', None) or getattr(lote.producto, 'tipo_producto', None) != 'palta':
                return None
            from inventory.models import StockReservation
            agg = StockReservation.objects.filter(
                item_venta_pendiente=obj,
                estado='en_proceso'
            ).aggregate(total=models.Sum('kg_reservados'))
            return agg['total'] or 0
        except Exception:
            return 0


class SalePendingSerializer(serializers.ModelSerializer):
    """Serializador para CREAR y LEER ventas pendientes."""
    # --- Campos para LECTURA (OUTPUT) ---
    items_read = SalePendingItemSerializer(many=True, source='items', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    vendedor_nombre = serializers.SerializerMethodField()
    
    # --- Campos para ESCRITURA (INPUT) ---
    cliente = serializers.SlugRelatedField(
        queryset=Customer.objects.all(), slug_field='uid', required=False, allow_null=True
    )
    items = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=True
    )

    class Meta:
        model = SalePending
        fields = (
            'uid', 'cliente', 'vendedor', 'metodo_pago', 'comentarios', 'business',
            'estado', 'total', 'cantidad_cajas', 'created_at',
            'items_read', 'items', 'codigo_venta',
            'cliente_nombre', 'vendedor_nombre',
            # Campos para escritura de cliente ocasional (no se leen)
            'nombre_cliente', 'rut_cliente', 'telefono_cliente', 'email_cliente',
        )
        read_only_fields = ('total', 'cantidad_cajas', 'created_at', 'cliente_nombre', 'vendedor_nombre')

    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return obj.nombre_cliente or "-"

    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            # Construye el nombre completo, o usa el username como fallback
            full_name = f"{obj.vendedor.first_name} {obj.vendedor.last_name}".strip()
            return full_name or obj.vendedor.username
        return "-"

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        if not items_data:
            raise serializers.ValidationError("El campo 'items_data' es requerido y no puede estar vacío.")

        # Limpiar datos del cliente ocasional si son nulos
        for field in ['nombre_cliente', 'rut_cliente', 'telefono_cliente', 'email_cliente']:
            if validated_data.get(field) is None:
                validated_data[field] = ''
        
        # Extraer vendedor y business que la vista nos pasa en .save()
        vendedor = validated_data.get('vendedor')
        business = validated_data.get('business')

        # Crear la instancia de SalePending con todos los datos (no forzar estado)
        # El **validated_data debe ir al final para que no se sobreescriba
        sale_pending = SalePending.objects.create(**validated_data)
        total_venta = Decimal('0.0')
        total_cajas = 0

        for item_data in items_data:
            lote_uid = item_data.get('lote')
            bin_uid = item_data.get('bin')
            if not lote_uid and not bin_uid:
                raise serializers.ValidationError("Cada item debe tener 'lote' o 'bin'.")
            if lote_uid and bin_uid:
                raise serializers.ValidationError("No se puede enviar 'lote' y 'bin' en el mismo item.")

            precio_unidad = Decimal(item_data.get('precio_unidad') or '0')
            precio_kg = Decimal(item_data.get('precio_kg') or '0')

            if lote_uid:
                try:
                    lote_obj = FruitLot.objects.get(uid=lote_uid)
                except FruitLot.DoesNotExist:
                    raise serializers.ValidationError(f"El lote con uid {lote_uid} no existe.")

                es_palta = lote_obj.producto.tipo_producto == 'palta'
                cajas_solicitadas = item_data.get('unidades_vendidas', 0) or 0
                kg_solicitados = Decimal(item_data.get('peso_vendido', '0') or '0')

                reservas_activas = StockReservation.objects.filter(lote=lote_obj, estado='en_proceso')
                cajas_ya_reservadas = reservas_activas.aggregate(total=Sum('cajas_reservadas'))['total'] or 0
                kg_ya_reservados = reservas_activas.aggregate(total=Sum('kg_reservados'))['total'] or Decimal('0.0')

                stock_cajas_disponible = lote_obj.cantidad_cajas - cajas_ya_reservadas
                stock_kg_disponible = lote_obj.peso_neto - kg_ya_reservados if lote_obj.peso_neto else Decimal('0.0')

                if stock_cajas_disponible < cajas_solicitadas:
                    raise serializers.ValidationError(f"Stock de cajas insuficiente para {lote_obj.uid}. Disponible: {stock_cajas_disponible}, Solicitado: {cajas_solicitadas}")
                if es_palta and stock_kg_disponible < kg_solicitados:
                    raise serializers.ValidationError(f"Stock de kg insuficiente para {lote_obj.uid}. Disponible: {stock_kg_disponible}, Solicitado: {kg_solicitados}")

                subtotal = (Decimal(cajas_solicitadas) * precio_unidad) + (kg_solicitados * precio_kg)

                pending_item = SalePendingItem.objects.create(
                    venta_pendiente=sale_pending,
                    lote=lote_obj,
                    cantidad_unidades=cajas_solicitadas,
                    precio_unidad=precio_unidad,
                    cantidad_kg=kg_solicitados,
                    precio_kg=precio_kg,
                    subtotal=subtotal
                )

                StockReservation.objects.create(
                    lote=lote_obj,
                    item_venta_pendiente=pending_item,
                    usuario=validated_data.get('vendedor'),
                    cajas_reservadas=cajas_solicitadas,
                    kg_reservados=kg_solicitados,
                    cliente=sale_pending.cliente,
                    nombre_cliente=sale_pending.nombre_cliente,
                    rut_cliente=sale_pending.rut_cliente,
                    telefono_cliente=sale_pending.telefono_cliente
                )

                total_venta += subtotal
                total_cajas += cajas_solicitadas

            else:
                # Item por Bin
                try:
                    bin_obj = FruitBin.objects.get(uid=bin_uid)
                except FruitBin.DoesNotExist:
                    raise serializers.ValidationError(f"El bin con uid {bin_uid} no existe.")

                if getattr(bin_obj, 'estado', None) != 'DISPONIBLE':
                    raise serializers.ValidationError("El bin no está disponible para pre-venta.")

                cajas_solicitadas = item_data.get('unidades_vendidas', 1) or 1
                kg_solicitados = Decimal(item_data.get('peso_vendido', '0') or '0')

                subtotal = (Decimal(cajas_solicitadas) * precio_unidad) + (kg_solicitados * precio_kg)

                # 1) Crear el item pendiente con el bin aún en DISPONIBLE (pasa validación del modelo)
                SalePendingItem.objects.create(
                    venta_pendiente=sale_pending,
                    bin=bin_obj,
                    cantidad_unidades=cajas_solicitadas,
                    precio_unidad=precio_unidad,
                    cantidad_kg=kg_solicitados,
                    precio_kg=precio_kg,
                    subtotal=subtotal
                )

                # 2) Inmediatamente marcar el bin como EN_PROCESO para ocultarlo del frontend
                bin_obj.estado = 'EN_PROCESO'
                try:
                    bin_obj.save(update_fields=['estado'])
                except Exception:
                    bin_obj.save()

                total_venta += subtotal
                total_cajas += cajas_solicitadas

        sale_pending.total = total_venta
        sale_pending.cantidad_cajas = total_cajas
        sale_pending.save()

        return sale_pending
    
    @transaction.atomic
    def update(self, instance, validated_data):
        from inventory.models import StockReservation
        from django.db import transaction
        from sales.models import Sale, SaleItem
        import logging
        logger = logging.getLogger(__name__)
        
        # Log para depuración
        logger.info(f"SalePendingSerializer.update: validated_data = {validated_data}")
        logger.info(f"SalePendingSerializer.update: instance.estado antes = {instance.estado}")

        # Solo actualizar el estado de la venta pendiente
        estado = validated_data.get('estado')
        comentarios = validated_data.get('comentarios')
        logger.info(f"SalePendingSerializer.update: estado recibido = {estado}")
        if estado:
            if estado == 'cancelada':
                # Cancelar la venta pendiente y liberar las reservas de stock
                logger.info(f"SalePendingSerializer.update: Cancelando venta pendiente {instance.uid}")
                StockReservation.objects.filter(item_venta_pendiente__venta_pendiente=instance).update(estado='cancelada')
                instance.estado = 'cancelada'
                # Si se proporcionan comentarios (razón de cancelación), actualizarlos
                if comentarios:
                    instance.comentarios = comentarios
                # Revertir bins a DISPONIBLE
                try:
                    for pending_item in instance.items.all():
                        if pending_item.bin:
                            pending_item.bin.estado = 'DISPONIBLE'
                            pending_item.bin.save(update_fields=['estado'])
                except Exception:
                    pass
                logger.info(f"SalePendingSerializer.update: Estado cambiado a {instance.estado}")
                instance.save()
                logger.info(f"SalePendingSerializer.update: Venta guardada, estado final = {instance.estado}")
                return instance
            
            elif estado == 'confirmada':
                # Convertir la venta pendiente en una venta directa
                with transaction.atomic():
                    # Validar stock disponible antes de confirmar la venta
                    for pending_item in instance.items.all():
                        if pending_item.lote:
                            lote = pending_item.lote
                            cajas_solicitadas = pending_item.cantidad_unidades
                            # Verificar stock disponible (sin contar las reservas que estamos por confirmar)
                            if lote.cantidad_cajas < cajas_solicitadas:
                                logger.error(f"Stock insuficiente para confirmar venta. Lote {lote.uid}: disponible={lote.cantidad_cajas}, solicitado={cajas_solicitadas}")
                                raise serializers.ValidationError(f"Stock insuficiente para confirmar venta. Lote {lote.uid}: disponible={lote.cantidad_cajas}, solicitado={cajas_solicitadas}")
                        elif pending_item.bin:
                            # Validar disponibilidad de bin (permitir EN_PROCESO por reserva de pendiente)
                            if getattr(pending_item.bin, 'estado', None) not in ('DISPONIBLE', 'EN_PROCESO'):
                                raise serializers.ValidationError("El bin ya no está disponible para confirmar la venta.")
                    
                    # Crear la venta
                    sale = Sale.objects.create(
                        cliente=instance.cliente,
                        vendedor=instance.vendedor,
                        metodo_pago=instance.metodo_pago,
                        total=instance.total,
                        business=instance.business
                    )
                    # Crear SaleItems a partir de los items pendientes
                    for pending_item in instance.items.all():
                        if pending_item.lote:
                            SaleItem.objects.create(
                                venta=sale,
                                lote=pending_item.lote,
                                unidades_vendidas=pending_item.cantidad_unidades,
                                precio_unidad=pending_item.precio_unidad,
                                peso_vendido=pending_item.cantidad_kg,
                                precio_kg=pending_item.precio_kg,
                                subtotal=pending_item.subtotal
                            )
                            # Marcar reservas como confirmadas
                            try:
                                StockReservation.objects.filter(item_venta_pendiente=pending_item, estado='en_proceso').update(estado='confirmada')
                            except Exception:
                                pass
                        elif pending_item.bin:
                            SaleItem.objects.create(
                                venta=sale,
                                bin=pending_item.bin,
                                unidades_vendidas=pending_item.cantidad_unidades,
                                precio_unidad=pending_item.precio_unidad,
                                peso_vendido=pending_item.cantidad_kg,
                                precio_kg=pending_item.precio_kg,
                                subtotal=pending_item.subtotal
                            )
                            # Marcar bin como VENDIDO
                            try:
                                pending_item.bin.estado = 'VENDIDO'
                                pending_item.bin.save(update_fields=['estado'])
                            except Exception:
                                pass
                    
                    # Si hay motivo de cancelación en los comentarios, guardarlo como motivo_cancelacion
                    instance.estado = 'confirmada'
                    instance.save()
                    
                return instance
        
        # Si no se proporciona un estado, simplemente actualizar los campos básicos
        instance.comentarios = validated_data.get('comentarios', instance.comentarios)
        instance.save()
        return instance

    def get_resumen(self, obj):
        try:
            from django.db.models import Sum
            cajas_por_lote = obj.items.filter(lote__isnull=False).aggregate(total=Sum('unidades_vendidas'))['total'] or 0
            bins_vendidos = obj.items.filter(bin__isnull=False).count()
            cajas_vacias = BoxType.objects.filter(business=obj.business).aggregate(total=Sum('stock_cajas_vacias'))['total'] or 0
            return {
                'cajas_por_lote': cajas_por_lote,
                'bins_vendidos': bins_vendidos,
                'cajas_vacias_en_bodega': cajas_vacias,
            }
        except Exception:
            return {
                'cajas_por_lote': 0,
                'bins_vendidos': 0,
                'cajas_vacias_en_bodega': 0,
            }
    
    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            return f"{obj.vendedor.first_name} {obj.vendedor.last_name}".strip() or obj.vendedor.username
        return None
    
    # def get_producto_nombre(self, obj):
    #     if obj.lote and obj.lote.producto:
    #         return obj.lote.producto.nombre
    #     return None
    
    # def get_calibre(self, obj):
    #     if obj.lote:
    #         return obj.lote.calibre
    #     return None
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        elif obj.nombre_cliente:
            return obj.nombre_cliente
        return None
        
    def get_lote_info(self, obj):
        """Devuelve toda la información del lote para el frontend"""
        if not obj.lote:
            return None
            
        from inventory.serializers import FruitLotSerializer

class ProductSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['uid', 'nombre', 'tipo_producto', 'marca']

class FruitLotSaleSerializer(serializers.ModelSerializer):
    producto = ProductSaleSerializer(read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.name', read_only=True)
    propietario_original_nombre = serializers.CharField(source='propietario_original.name', read_only=True, allow_null=True)

    class Meta:
        model = FruitLot
        fields = [
            'uid', 
            'producto',
            'variedad',
            'proveedor_nombre',
            'propietario_original_nombre',
            'calibre',
            'fecha_ingreso',
            'en_concesion'
        ]

class SaleItemSerializer(serializers.ModelSerializer):
    lote = FruitLotSaleSerializer(read_only=True)
    lote_id = serializers.PrimaryKeyRelatedField(
        queryset=FruitLot.objects.all(), source='lote', write_only=True
    )
    # Usar detalle de bin para respuestas más informativas
    bin = FruitBinDetailSerializer(read_only=True)
    bin_id = serializers.PrimaryKeyRelatedField(
        queryset=FruitBin.objects.all(), source='bin', write_only=True
    )

    class Meta:
        model = SaleItem
        fields = [
            'uid',
            'lote',
            'lote_id',
            'bin',
            'bin_id',
            'unidades_vendidas',
            'peso_vendido',
            'precio_unidad',
            'precio_kg',
            'subtotal',
            'es_concesion'
        ]

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    cliente = serializers.SlugRelatedField(queryset=Customer.objects.all(), slug_field='uid')
    vendedor_nombre = serializers.CharField(source='vendedor.username', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_pago_display', read_only=True)
    resumen = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Sale
        fields = (
            'uid', 'codigo_venta', 'cliente', 'cliente_nombre', 'vendedor', 'vendedor_nombre', 'metodo_pago',
            'total', 'pagado', 'saldo_pendiente', 'estado_pago', 'estado_display',
            'fecha_vencimiento', 'created_at', 'items', 'resumen'
        )
        read_only_fields = ('vendedor',)

    @transaction.atomic
    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        items_data = validated_data.pop('items')
        # Aceptar items enviados como string JSON en form-data
        # Ej: items='[{"bin":"uuid","peso_vendido":459,"precio_kg":1900,"subtotal":872100,"unidades_vendidas":1}]'
        if isinstance(items_data, str):
            try:
                loaded = json.loads(items_data)
                # Si viene un objeto único, envolverlo en lista
                if isinstance(loaded, dict):
                    items_data = [loaded]
                elif isinstance(loaded, list):
                    items_data = loaded
                else:
                    raise ValueError("El JSON de 'items' debe ser lista u objeto")
            except Exception as e:
                logger.error(f"Error parseando 'items' como JSON: {e}")
                raise serializers.ValidationError("Formato inválido para 'items'. Debe ser una lista JSON o un objeto JSON.")
        if not isinstance(items_data, list):
            items_data = list(items_data) if items_data is not None else []

        def D(v):
            from decimal import Decimal
            try:
                return Decimal(str(v or 0))
            except Exception:
                return Decimal('0')

        perfil = self.context['request'].user.perfil

        # Validaciones mínimas: existencia de lote/bin y stock para lote, disponibilidad para bin
        for raw in items_data:
            lote_uid = raw.get('lote') or raw.get('lote_id')
            bin_uid = raw.get('bin')
            if not lote_uid and not bin_uid:
                raise serializers.ValidationError("Cada item debe tener 'lote' o 'bin'.")
            if lote_uid and bin_uid:
                raise serializers.ValidationError("No se puede enviar 'lote' y 'bin' en el mismo item.")
            if lote_uid:
                try:
                    lote = FruitLot.objects.get(uid=lote_uid)
                except FruitLot.DoesNotExist:
                    raise serializers.ValidationError(f"El lote con uid {lote_uid} no existe.")
                unidades_vendidas = int(raw.get('unidades_vendidas') or 0)
                if unidades_vendidas > getattr(lote, 'cantidad_cajas', 0):
                    raise serializers.ValidationError(
                        f"No hay suficiente stock. Intentando vender {unidades_vendidas} cajas cuando solo hay {lote.cantidad_cajas} disponibles en lote {lote.uid}."
                    )
            else:
                try:
                    bin_obj = FruitBin.objects.get(uid=bin_uid)
                except FruitBin.DoesNotExist:
                    raise serializers.ValidationError(f"El bin con uid {bin_uid} no existe.")
                if getattr(bin_obj, 'estado', None) != 'DISPONIBLE':
                    raise serializers.ValidationError("El bin no está disponible para venta.")

        # Crear la venta
        sale = Sale.objects.create(vendedor=self.context['request'].user, business=perfil.business, **validated_data)
        total_venta = D(0)

        # Crear los items
        for raw in items_data:
            lote_uid = raw.get('lote') or raw.get('lote_id')
            bin_uid = raw.get('bin')
            unidades_vendidas = int(raw.get('unidades_vendidas') or (1 if bin_uid else 0))
            peso_vendido = D(raw.get('peso_vendido'))
            precio_unidad = D(raw.get('precio_unidad'))
            precio_kg = D(raw.get('precio_kg'))
            subtotal_calc = (D(unidades_vendidas) * precio_unidad) + (peso_vendido * precio_kg)

            if lote_uid:
                lote = FruitLot.objects.get(uid=lote_uid)
                item = SaleItem.objects.create(
                    venta=sale,
                    lote=lote,
                    unidades_vendidas=unidades_vendidas,
                    precio_unidad=precio_unidad,
                    peso_vendido=peso_vendido,
                    precio_kg=precio_kg,
                    es_concesion=bool(raw.get('es_concesion', False)),
                    subtotal=subtotal_calc
                )
            else:
                bin_obj = FruitBin.objects.get(uid=bin_uid)
                item = SaleItem.objects.create(
                    venta=sale,
                    bin=bin_obj,
                    unidades_vendidas=unidades_vendidas or 1,
                    precio_unidad=precio_unidad,
                    peso_vendido=peso_vendido,
                    precio_kg=precio_kg,
                    es_concesion=False,
                    subtotal=subtotal_calc
                )

            total_venta += item.subtotal

        sale.total = total_venta
        sale.saldo_pendiente = total_venta
        sale.save()
        return sale

    def get_resumen(self, obj):
        try:
            from django.db.models import Sum
            cajas_por_lote = obj.items.filter(lote__isnull=False).aggregate(total=Sum('unidades_vendidas'))['total'] or 0
            bins_vendidos = obj.items.filter(bin__isnull=False).count()
            cajas_vacias = BoxType.objects.filter(business=obj.business).aggregate(total=Sum('stock_cajas_vacias'))['total'] or 0
            return {
                'cajas_por_lote': cajas_por_lote,
                'bins_vendidos': bins_vendidos,
                'cajas_vacias_en_bodega': cajas_vacias,
            }
        except Exception:
            return {
                'cajas_por_lote': 0,
                'bins_vendidos': 0,
                'cajas_vacias_en_bodega': 0,
            }

class SaleSerializer(serializers.ModelSerializer):
    vendedor_nombre = serializers.SerializerMethodField()
    cliente_nombre = serializers.SerializerMethodField()
    estado_pago_display = serializers.SerializerMethodField()
    pagos_asociados = serializers.SerializerMethodField()
    # Campos de cancelación
    cancelada_por_nombre = serializers.SerializerMethodField()
    autorizada_por_nombre = serializers.SerializerMethodField()
    estado_display = serializers.SerializerMethodField()
    # Campos de concesión
    proveedor_original_nombre = serializers.SerializerMethodField()
    # Nuevo campo para items de venta
    items = SaleItemSerializer(many=True, required=False)
    # Resumen de la venta
    resumen = serializers.SerializerMethodField(read_only=True)

    # Configurar campos para aceptar UUIDs
    cliente = serializers.SlugRelatedField(queryset=Customer.objects.all(), slug_field='uid', required=False, allow_null=True)

    class Meta:
        model = Sale
        fields = (
            'uid', 'codigo_venta', 'cliente', 'vendedor', 'cajas_vendidas', 'total',
            'metodo_pago', 'comprobante', 'business', 'pagado', 'fecha_vencimiento',
            'saldo_pendiente', 'estado_pago', 'estado_pago_display', 'pagos_asociados',
            'vendedor_nombre', 'cliente_nombre', 'items', 'resumen',
            # Campos de cancelación
            'cancelada', 'fecha_cancelacion', 'motivo_cancelacion', 'cancelada_por', 'autorizada_por',
            'cancelada_por_nombre', 'autorizada_por_nombre', 'estado_display',
            # Campos de concesión
            'es_concesion', 'comision_ganada', 'proveedor_original', 'proveedor_original_nombre',
            'created_at', 'updated_at'
        )
        read_only_fields = ('business', 'pagado', 'saldo_pendiente', 'items')

    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            return f"{obj.vendedor.first_name} {obj.vendedor.last_name}".strip() or obj.vendedor.username
        return None

    def get_producto_nombre(self, obj):
        first_item = obj.items.first()
        if first_item and first_item.lote and first_item.lote.producto:
            return first_item.lote.producto.nombre
        return None

    def get_calibre(self, obj):
        first_item = obj.items.first()
        if first_item and first_item.lote:
            return first_item.lote.calibre
        return None

    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return None

    def get_estado_pago_display(self, obj):
        """Devuelve una versión legible del estado de pago"""
        estados = {
            'pendiente': 'Pendiente',
            'parcial': 'Pago Parcial',
            'completo': 'Pagado',
            'cerrada': 'Cerrada'
        }
        return estados.get(obj.estado_pago, 'Desconocido')

    def get_pagos_asociados(self, obj):
        """Devuelve información resumida de los pagos asociados a esta venta"""
        # Usar la relación many-to-many correcta (related_name='pagos')
        pagos = obj.pagos.all().order_by('-created_at')
        return [{
            'uid': pago.uid,
            'fecha': pago.created_at,
            'monto': pago.monto,
            'metodo_pago': pago.metodo_pago,
            'referencia': pago.referencia
        } for pago in pagos]

    def get_cancelada_por_nombre(self, obj):
        """Devuelve el nombre del usuario que canceló la venta"""
        if obj.cancelada_por:
            return f"{obj.cancelada_por.first_name} {obj.cancelada_por.last_name}".strip() or obj.cancelada_por.username
        return None

    def get_autorizada_por_nombre(self, obj):
        """Devuelve el nombre del usuario que autorizó la cancelación"""
        if obj.autorizada_por:
            return f"{obj.autorizada_por.first_name} {obj.autorizada_por.last_name}".strip() or obj.autorizada_por.username
        return None

    def get_estado_display(self, obj):
        """Devuelve el estado de la venta considerando si está cancelada"""
        return obj.estado_display

    def get_proveedor_original_nombre(self, obj):
        """Devuelve el nombre del proveedor original para ventas en concesión"""
        if obj.es_concesion and obj.proveedor_original:
            return obj.proveedor_original.nombre
        return None

    def get_resumen(self, obj):
        try:
            cajas_por_lote = obj.items.filter(lote__isnull=False).aggregate(total=Sum('unidades_vendidas'))['total'] or 0
            bins_vendidos = obj.items.filter(bin__isnull=False).count()
            cajas_vacias = BoxType.objects.filter(business=obj.business).aggregate(total=Sum('stock_cajas_vacias'))['total'] or 0
            return {
                'cajas_por_lote': cajas_por_lote,
                'bins_vendidos': bins_vendidos,
                'cajas_vacias_en_bodega': cajas_vacias,
            }
        except Exception:
            return {
                'cajas_por_lote': 0,
                'bins_vendidos': 0,
                'cajas_vacias_en_bodega': 0,
            }

    def create(self, validated_data):
        # El vendedor y el negocio se asignan en la vista (perform_create)
        items_data = self.context['request'].data.get('items', '[]')
        if isinstance(items_data, str):
            items_data = json.loads(items_data)

        # Calcular el total de la venta sumando los subtotales de cada item (bin o lote)
        def D(v):
            try:
                return Decimal(str(v or 0))
            except Exception:
                return Decimal('0')
        total = Decimal('0')
        for item in items_data:
            # Si no viene subtotal, calcularlo
            if item.get('subtotal') is None:
                unidades = int(item.get('unidades_vendidas') or (1 if item.get('bin') else 0))
                subtotal_calc = D(unidades) * D(item.get('precio_unidad')) + D(item.get('peso_vendido')) * D(item.get('precio_kg'))
                item['subtotal'] = str(subtotal_calc)
            total += D(item.get('subtotal'))
        validated_data['total'] = total

        # Calcular el total de cajas vendidas sumando las cajas de cada item (para bin por defecto 1)
        cajas_vendidas = 0
        for item in items_data:
            if item.get('bin'):
                cajas_vendidas += int(item.get('unidades_vendidas') or 1)
            else:
                cajas_vendidas += int(item.get('unidades_vendidas') or 0)
        validated_data['cajas_vendidas'] = cajas_vendidas

        # Crear la venta
        venta = Sale.objects.create(**validated_data)

        # Crear los items de la venta
        for item_data in items_data:
            # Soportar items por lote o por bin
            if item_data.get('bin'):
                try:
                    bin_obj = FruitBin.objects.get(uid=item_data.get('bin'))
                    SaleItem.objects.create(
                        venta=venta,
                        bin=bin_obj,
                        unidades_vendidas=item_data.get('unidades_vendidas') or 1,
                        precio_unidad=item_data.get('precio_unidad') or 0,
                        peso_vendido=item_data.get('peso_vendido') or 0,
                        precio_kg=item_data.get('precio_kg') or 0,
                        subtotal=item_data.get('subtotal') or 0,
                        es_concesion=False
                    )
                except FruitBin.DoesNotExist:
                    # Ignorar items con bin inválido
                    continue
            else:
                try:
                    item_payload = {
                        'lote': FruitLot.objects.get(uid=item_data.get('lote')),
                        'unidades_vendidas': item_data.get('unidades_vendidas', 0) or 0,
                        'precio_unidad': item_data.get('precio_unidad', 0) or 0,
                        'peso_vendido': item_data.get('peso_vendido', 0) or 0,
                        'precio_kg': item_data.get('precio_kg', 0) or 0,
                        'subtotal': item_data.get('subtotal', 0) or 0,
                        'es_concesion': item_data.get('es_concesion', False)
                    }
                    SaleItem.objects.create(venta=venta, **item_payload)
                except FruitLot.DoesNotExist:
                    # Si un lote no existe, simplemente no se añade ese item
                    continue
        
        return venta

    def update(self, instance, validated_data):
        """Actualiza una venta y sus items"""
        items_data = self.context['request'].data.get('items', '[]')
        if isinstance(items_data, str):
            items_data = json.loads(items_data)
        
        # Actualizar campos de la venta principal
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Recalcular total y cajas (soportando bin o lote)
        def D(v):
            try:
                return Decimal(str(v or 0))
            except Exception:
                return Decimal('0')
        total = Decimal('0')
        cajas_vendidas = 0
        for item in items_data:
            if item.get('subtotal') is None:
                unidades = int(item.get('unidades_vendidas') or (1 if item.get('bin') else 0))
                subtotal_calc = D(unidades) * D(item.get('precio_unidad')) + D(item.get('peso_vendido')) * D(item.get('precio_kg'))
                item['subtotal'] = str(subtotal_calc)
            total += D(item.get('subtotal'))
            if item.get('bin'):
                cajas_vendidas += int(item.get('unidades_vendidas') or 1)
            else:
                cajas_vendidas += int(item.get('unidades_vendidas') or 0)
        instance.total = total
        instance.cajas_vendidas = cajas_vendidas

        # Actualizar items
        instance.items.all().delete()
        for item_data in items_data:
            if item_data.get('bin'):
                try:
                    bin_obj = FruitBin.objects.get(uid=item_data.get('bin'))
                    SaleItem.objects.create(
                        venta=instance,
                        bin=bin_obj,
                        unidades_vendidas=item_data.get('unidades_vendidas') or 1,
                        precio_unidad=item_data.get('precio_unidad') or 0,
                        peso_vendido=item_data.get('peso_vendido') or 0,
                        precio_kg=item_data.get('precio_kg') or 0,
                        subtotal=item_data.get('subtotal') or 0,
                        es_concesion=False
                    )
                except FruitBin.DoesNotExist:
                    continue
            else:
                try:
                    item_payload = {
                        'lote': FruitLot.objects.get(uid=item_data.get('lote')),
                        'unidades_vendidas': item_data.get('unidades_vendidas', 0) or 0,
                        'precio_unidad': item_data.get('precio_unidad', 0) or 0,
                        'peso_vendido': item_data.get('peso_vendido', 0) or 0,
                        'precio_kg': item_data.get('precio_kg', 0) or 0,
                        'subtotal': item_data.get('subtotal', 0) or 0,
                        'es_concesion': item_data.get('es_concesion', False)
                    }
                    SaleItem.objects.create(venta=instance, **item_payload)
                except FruitLot.DoesNotExist:
                    continue
        
        instance.save()
        return instance


class SaleListSerializer(serializers.ModelSerializer):
    """
    Serializador optimizado para listar ventas. Devuelve los datos esenciales
    y los items de la venta para una experiencia de usuario enriquecida.
    """
    cliente_nombre = serializers.SerializerMethodField()
    vendedor_nombre = serializers.SerializerMethodField()
    estado_pago_display = serializers.CharField(source='get_estado_pago_display', read_only=True)
    items = SaleItemSerializer(many=True, read_only=True)
    class Meta:
        model = Sale
        fields = (
            'uid',
            'codigo_venta',
            'created_at',
            'cliente_nombre',
            'vendedor_nombre',
            'total',
            'items',
            'estado_pago',
            'estado_pago_display',
            'metodo_pago',
            'cancelada'
        )

    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return None

    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            return f"{obj.vendedor.first_name} {obj.vendedor.last_name}".strip() or obj.vendedor.username
        return None



