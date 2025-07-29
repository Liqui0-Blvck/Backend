from rest_framework import serializers
from django.db import models
from .models import Sale, SalePending, Customer, CustomerPayment
from accounts.serializers import CustomUserSerializer
from inventory.models import FruitLot


class CustomerSerializer(serializers.ModelSerializer):
    credito_disponible = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    pagos_pendientes = serializers.IntegerField(read_only=True)
    ultimas_compras = serializers.SerializerMethodField(read_only=True)
    ultimos_pagos = serializers.SerializerMethodField(read_only=True)
    resumen_credito = serializers.SerializerMethodField(read_only=True)
    
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
            'producto': venta.lote.producto.nombre if venta.lote and venta.lote.producto else None,
            'peso_vendido': venta.peso_vendido
        } for venta in ultimas_compras]
    
    def get_ultimos_pagos(self, obj):
        # Obtener los últimos 5 pagos del cliente
        ultimos_pagos = obj.pagos.all().order_by('-created_at')[:5]
        return [{
            'uid': pago.uid,
            'fecha': pago.created_at,
            'monto': pago.monto,
            'metodo_pago': pago.metodo_pago,
            'referencia': pago.referencia
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
        
        return {
            'total_compras_credito': total_compras,
            'total_pagos': total_pagos,
            'monto_total_compras': monto_total_compras,
            'monto_total_pagos': monto_total_pagos,
            'saldo_actual': obj.saldo_actual,
            'credito_disponible': obj.credito_disponible,
            'limite_credito': obj.limite_credito
        }


class CustomerPaymentSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CustomerPayment
        fields = '__all__'
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return None


class SalePendingSerializer(serializers.ModelSerializer):
    # Campos adicionales para mostrar información relacionada
    vendedor_nombre = serializers.SerializerMethodField()
    producto_nombre = serializers.SerializerMethodField()
    calibre = serializers.SerializerMethodField()
    cliente_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = SalePending
        fields = '__all__'
    
    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            return f"{obj.vendedor.first_name} {obj.vendedor.last_name}".strip() or obj.vendedor.username
        return None
    
    def get_producto_nombre(self, obj):
        if obj.lote and obj.lote.producto:
            return obj.lote.producto.nombre
        return None
    
    def get_calibre(self, obj):
        if obj.lote:
            return obj.lote.calibre
        return None
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        elif obj.nombre_cliente:
            return obj.nombre_cliente
        return None

class SaleSerializer(serializers.ModelSerializer):
    vendedor_nombre = serializers.SerializerMethodField()
    producto_nombre = serializers.SerializerMethodField()
    calibre = serializers.SerializerMethodField()
    cliente_nombre = serializers.SerializerMethodField()

    # Configurar campos para aceptar UUIDs
    lote = serializers.SlugRelatedField(queryset=FruitLot.objects.all(), slug_field='uid')
    cliente = serializers.SlugRelatedField(queryset=Customer.objects.all(), slug_field='uid', required=False, allow_null=True)

    class Meta:
        model = Sale
        fields = (
            'uid', 'codigo_venta', 'lote', 'cliente', 'vendedor', 'peso_vendido', 'cajas_vendidas', 'precio_kg', 'total',
            'metodo_pago', 'comprobante', 'business',
            'vendedor_nombre', 'producto_nombre', 'calibre', 'cliente_nombre',
        )
    
    def get_vendedor_nombre(self, obj):
        if obj.vendedor:
            return f"{obj.vendedor.first_name} {obj.vendedor.last_name}".strip() or obj.vendedor.username
        return None
    
    def get_producto_nombre(self, obj):
        if obj.lote and obj.lote.producto:
            return obj.lote.producto.nombre
        return None
    
    def get_calibre(self, obj):
        if obj.lote:
            return obj.lote.calibre
        return None
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return None
