from rest_framework import serializers
from .models import Sale, SalePending, Customer
from accounts.serializers import CustomUserSerializer
from inventory.models import FruitLot


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


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
    cliente = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)

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
