from rest_framework import serializers
from decimal import Decimal
import json
from django.db import models, transaction
from django.db.models import Sum
from .models import Sale, SalePending, SalePendingItem, Customer, CustomerPayment, SaleItem
from accounts.serializers import CustomUserSerializer
from inventory.models import FruitLot, StockReservation, Product
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
    producto_nombre = serializers.CharField(source='lote.producto.nombre', read_only=True)
    calibre = serializers.CharField(source='lote.calibre.nombre', read_only=True)
    lote = serializers.CharField(source='lote.uid', read_only=True)
    # Detalle completo del lote para que el frontend tenga toda la info de origen
    lote_detalle = serializers.SerializerMethodField(read_only=True)
    # Cantidades reservadas asociadas a este item pendiente
    cajas_reservadas = serializers.SerializerMethodField(read_only=True)
    kg_reservados = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SalePendingItem
        fields = [
            'uid', 'lote', 'producto_nombre', 'calibre', 'lote_detalle',
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
            # Si el producto no es palta, no mostramos kilos reservados
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

        # Crear la instancia de SalePending con todos los datos
        # El **validated_data debe ir al final para que no se sobreescriba
        sale_pending = SalePending.objects.create(**validated_data)
        total_venta = Decimal('0.0')
        total_cajas = 0

        for item_data in items_data:
            lote_uid = item_data.get('lote')
            if not lote_uid:
                raise serializers.ValidationError("Cada item debe tener un 'lote'.")
            try:
                lote_obj = FruitLot.objects.get(uid=lote_uid)
            except FruitLot.DoesNotExist:
                raise serializers.ValidationError(f"El lote con uid {lote_uid} no existe.")

            es_palta = lote_obj.producto.tipo_producto == 'palta'

            # --- LECTURA CORRECTA DEL PAYLOAD ---
            cajas_solicitadas = item_data.get('unidades_vendidas', 0) or 0
            kg_solicitados = Decimal(item_data.get('peso_vendido', '0') or '0')
            unidades_solicitadas = cajas_solicitadas if not es_palta else 0

            # --- VALIDACIÓN DE STOCK ---
            reservas_activas = StockReservation.objects.filter(lote=lote_obj, estado='en_proceso')
            cajas_ya_reservadas = reservas_activas.aggregate(total=Sum('cajas_reservadas'))['total'] or 0
            kg_ya_reservados = reservas_activas.aggregate(total=Sum('kg_reservados'))['total'] or Decimal('0.0')

            # Simplificar la validación: solo verificar cajas disponibles para todos los productos
            stock_cajas_disponible = lote_obj.cantidad_cajas - cajas_ya_reservadas
            stock_kg_disponible = lote_obj.peso_neto - kg_ya_reservados if lote_obj.peso_neto else Decimal('0.0')

            if stock_cajas_disponible < cajas_solicitadas:
                raise serializers.ValidationError(f"Stock de cajas insuficiente para {lote_obj.uid}. Disponible: {stock_cajas_disponible}, Solicitado: {cajas_solicitadas}")
            if es_palta and stock_kg_disponible < kg_solicitados:
                raise serializers.ValidationError(f"Stock de kg insuficiente para {lote_obj.uid}. Disponible: {stock_kg_disponible}, Solicitado: {kg_solicitados}")

            # --- CÁLCULO Y CREACIÓN ---
            precio_unidad = Decimal(item_data.get('precio_unidad') or '0')
            precio_kg = Decimal(item_data.get('precio_kg') or '0')
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
                logger.info(f"SalePendingSerializer.update: Estado cambiado a {instance.estado}")
                instance.save()
                logger.info(f"SalePendingSerializer.update: Venta guardada, estado final = {instance.estado}")
                return instance
            
            elif estado == 'confirmada':
                # Convertir la venta pendiente en una venta directa
                with transaction.atomic():
                    # Validar stock disponible antes de confirmar la venta
                    for pending_item in instance.items.all():
                        lote = pending_item.lote
                        cajas_solicitadas = pending_item.cantidad_unidades
                        
                        # Verificar stock disponible (sin contar las reservas que estamos por confirmar)
                        if lote.cantidad_cajas < cajas_solicitadas:
                            logger.error(f"Stock insuficiente para confirmar venta. Lote {lote.uid}: disponible={lote.cantidad_cajas}, solicitado={cajas_solicitadas}")
                            raise serializers.ValidationError(f"Stock insuficiente para confirmar venta. Lote {lote.uid}: disponible={lote.cantidad_cajas}, solicitado={cajas_solicitadas}")
                    
                    # Crear la venta
                    sale = Sale.objects.create(
                        cliente=instance.cliente,
                        vendedor=instance.vendedor,
                        metodo_pago=instance.metodo_pago,
                        total=instance.total,
                        business=instance.business
                    )
                    
                    # Si hay motivo de cancelación en los comentarios, guardarlo como motivo_cancelacion
                    if instance.comentarios:
                        sale.motivo_cancelacion = instance.comentarios
                        sale.save(update_fields=['motivo_cancelacion'])
                    
                    # Crear los items de venta y actualizar el inventario
                    for pending_item in instance.items.all():
                        # Crear el SaleItem con los campos correctos según el modelo
                        logger.info(f"Creando SaleItem para lote {pending_item.lote.uid}: cajas={pending_item.cantidad_unidades}, stock actual={pending_item.lote.cantidad_cajas}")
                        SaleItem.objects.create(
                            venta=sale,
                            lote=pending_item.lote,
                            unidades_vendidas=pending_item.cantidad_unidades,
                            precio_unidad=pending_item.precio_unidad,
                            peso_vendido=pending_item.cantidad_kg,
                            precio_kg=pending_item.precio_kg,
                            subtotal=pending_item.subtotal
                        )
                    
                    # Marcar las reservas como completadas
                    StockReservation.objects.filter(item_venta_pendiente__venta_pendiente=instance).update(estado='completada')
                    
                    # Actualizar el estado de la venta pendiente
                    instance.estado = 'confirmada'
                    instance.save()
                    
                return instance
        
        # Si no se proporciona un estado, simplemente actualizar los campos básicos
        instance.comentarios = validated_data.get('comentarios', instance.comentarios)
        instance.save()
        return instance
    
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

    class Meta:
        model = SaleItem
        fields = [
            'uid',
            'lote',
            'lote_id',
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

    class Meta:
        model = Sale
        fields = (
            'uid', 'codigo_venta', 'cliente', 'cliente_nombre', 'vendedor', 'vendedor_nombre', 'metodo_pago',
            'total', 'pagado', 'saldo_pendiente', 'estado_pago', 'estado_display',
            'fecha_vencimiento', 'created_at', 'items'
        )
        read_only_fields = ('vendedor',)

    @transaction.atomic
    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        items_data = validated_data.pop('items')
        perfil = self.context['request'].user.perfil
        
        # Validar stock disponible antes de crear la venta
        for item_data in items_data:
            lote = item_data['lote']
            unidades_vendidas = item_data.get('unidades_vendidas', 0)
            
            # Verificar que hay suficiente stock
            if unidades_vendidas > lote.cantidad_cajas:
                logger.error(f"SaleSerializer.create: Error - Intentando vender {unidades_vendidas} cajas cuando solo hay {lote.cantidad_cajas} disponibles en lote {lote.uid}")
                raise serializers.ValidationError(f"No hay suficiente stock. Intentando vender {unidades_vendidas} cajas cuando solo hay {lote.cantidad_cajas} disponibles en lote {lote.uid}.")
        
        # Crear la venta
        sale = Sale.objects.create(vendedor=self.context['request'].user, business=perfil.business, **validated_data)
        total_venta = Decimal('0.0')

        # Crear los items de venta
        for item_data in items_data:
            logger.info(f"Creando SaleItem para lote {item_data['lote'].uid}: cajas={item_data.get('unidades_vendidas', 0)}, stock actual={item_data['lote'].cantidad_cajas}")
            # Mapeo explícito para garantizar que los datos del payload se asignan correctamente
            sale_item = SaleItem.objects.create(
                sale=sale,
                lote=item_data['lote'],
                unidades_vendidas=item_data.get('unidades_vendidas', 0),
                precio_unidad=item_data.get('precio_unidad', Decimal('0.0')),
                peso_vendido=item_data.get('peso_vendido', Decimal('0.0')),
                precio_kg=item_data.get('precio_kg', Decimal('0.0')),
                es_concesion=item_data.get('es_concesion', False)
            )
            total_venta += sale_item.subtotal

        sale.total = total_venta
        sale.saldo_pendiente = total_venta
        sale.save()
        return sale

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

    # Configurar campos para aceptar UUIDs
    cliente = serializers.SlugRelatedField(queryset=Customer.objects.all(), slug_field='uid', required=False, allow_null=True)

    class Meta:
        model = Sale
        fields = (
            'uid', 'codigo_venta', 'cliente', 'vendedor', 'cajas_vendidas', 'total',
            'metodo_pago', 'comprobante', 'business', 'pagado', 'fecha_vencimiento',
            'saldo_pendiente', 'estado_pago', 'estado_pago_display', 'pagos_asociados',
            'vendedor_nombre', 'cliente_nombre', 'items',
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

    def create(self, validated_data):
        # El vendedor y el negocio se asignan en la vista (perform_create)
        items_data = self.context['request'].data.get('items', '[]')
        if isinstance(items_data, str):
            items_data = json.loads(items_data)

        # Calcular el total de la venta sumando los subtotales de cada item
        total = sum(Decimal(item.get('subtotal') or 0) for item in items_data)
        validated_data['total'] = total

        # Calcular el total de cajas vendidas sumando las cajas de cada item
        cajas_vendidas = sum(int(item.get('unidades_vendidas') or 0) for item in items_data)
        validated_data['cajas_vendidas'] = cajas_vendidas

        # Crear la venta
        venta = Sale.objects.create(**validated_data)

        # Crear los items de la venta
        for item_data in items_data:
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
                pass
        
        return venta

    def update(self, instance, validated_data):
        """Actualiza una venta y sus items"""
        items_data = self.context['request'].data.get('items', '[]')
        if isinstance(items_data, str):
            items_data = json.loads(items_data)
        
        # Actualizar campos de la venta principal
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Recalcular total y cajas
        total = sum(Decimal(item.get('subtotal') or 0) for item in items_data)
        cajas_vendidas = sum(int(item.get('unidades_vendidas') or 0) for item in items_data)
        instance.total = total
        instance.cajas_vendidas = cajas_vendidas

        # Actualizar items
        instance.items.all().delete()
        for item_data in items_data:
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
                # Si un lote no existe, simplemente no se añade ese item
                pass
        
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



