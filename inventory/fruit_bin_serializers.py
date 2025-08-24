from rest_framework import serializers
from .models import FruitBin, ReceptionDetail, Product, Supplier, GoodsReception
from .serializers import ProductSerializer
import uuid
from django.shortcuts import get_object_or_404

class FruitBinListSerializer(serializers.ModelSerializer):
    """Serializador para listar bins de fruta con información resumida"""
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_tipo = serializers.CharField(source='producto.tipo_producto', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    peso_neto = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    calidad_display = serializers.CharField(source='get_calidad_display', read_only=True)
    
    class Meta:
        model = FruitBin
        fields = [
            'uid', 'codigo', 'producto', 'producto_nombre', 'producto_tipo', 'variedad',
            'peso_bruto', 'peso_tara', 'peso_neto', 'estado', 'estado_display',
            'calidad', 'calidad_display', 'proveedor', 'proveedor_nombre', 'fecha_recepcion'
        ]
    
    def get_peso_neto(self, obj):
        return obj.peso_neto


class FruitBinDetailSerializer(serializers.ModelSerializer):
    """Serializador detallado para bins de fruta con toda la información"""
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_tipo = serializers.CharField(source='producto.tipo_producto', read_only=True)
    producto_info = ProductSerializer(source='producto', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    proveedor_info = serializers.SerializerMethodField()
    peso_neto = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    calidad_display = serializers.CharField(source='get_calidad_display', read_only=True)
    recepcion_info = serializers.SerializerMethodField()
    
    class Meta:
        model = FruitBin
        fields = [
            'uid', 'codigo', 'producto', 'producto_nombre', 'producto_tipo', 'producto_info', 'variedad',
            'peso_bruto', 'peso_tara', 'peso_neto', 'estado', 'estado_display',
            'calidad', 'calidad_display', 'recepcion', 'recepcion_info', 'fecha_recepcion',
            'proveedor', 'proveedor_nombre', 'proveedor_info', 'temperatura', 'observaciones',
            'created_at', 'updated_at'
        ]
    
    def get_peso_neto(self, obj):
        return obj.peso_neto
    
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
    
    def get_recepcion_info(self, obj):
        """Retorna información básica de la recepción"""
        if obj.recepcion:
            return {
                'uid': obj.recepcion.uid,
                'numero_guia': obj.recepcion.numero_guia,
                'fecha_recepcion': obj.recepcion.fecha_recepcion
            }
        return None


class FruitBinBulkCreateSerializer(serializers.Serializer):
    """Serializador para la creación masiva de bins de fruta"""
    cantidad = serializers.IntegerField(min_value=1, required=True, help_text='Cantidad de bins a crear')
    producto = serializers.UUIDField(required=True, help_text='ID del producto')
    variedad = serializers.CharField(required=False, allow_blank=True, help_text='Variedad de la fruta')
    peso_bruto = serializers.DecimalField(max_digits=10, decimal_places=2, required=True, help_text='Peso bruto en kg')
    peso_tara = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, help_text='Peso de la tara en kg')
    estado = serializers.ChoiceField(choices=FruitBin.ESTADO_CHOICES, default='DISPONIBLE', help_text='Estado del bin')
    calidad = serializers.ChoiceField(choices=ReceptionDetail.CALIDAD_CHOICES, default=3, help_text='Calidad de la fruta')
    proveedor = serializers.UUIDField(required=False, allow_null=True, help_text='ID del proveedor')
    recepcion = serializers.UUIDField(required=False, allow_null=True, help_text='ID de la recepción')
    fecha_recepcion = serializers.DateField(required=False, help_text='Fecha de recepción')
    temperatura = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True, help_text='Temperatura de la fruta')
    observaciones = serializers.CharField(required=False, allow_blank=True, help_text='Observaciones adicionales')
    
    def create(self, validated_data):
        """Crea múltiples bins con los mismos datos"""
        cantidad = validated_data.pop('cantidad')
        business = validated_data.pop('business', None)
        
        # Convertir UUIDs a instancias de modelos
        producto_uuid = validated_data.pop('producto')
        producto = get_object_or_404(Product, uid=producto_uuid)
        
        # Manejar el proveedor (opcional)
        proveedor = None
        if 'proveedor' in validated_data and validated_data['proveedor']:
            proveedor_uuid = validated_data.pop('proveedor')
            proveedor = get_object_or_404(Supplier, uid=proveedor_uuid)
        
        # Manejar la recepción (opcional)
        recepcion = None
        if 'recepcion' in validated_data and validated_data['recepcion']:
            recepcion_uuid = validated_data.pop('recepcion')
            recepcion = get_object_or_404(GoodsReception, uid=recepcion_uuid)
        
        bins_creados = []
        for i in range(cantidad):
            # Generar un código único para cada bin
            codigo = f"BIN-{uuid.uuid4().hex[:8].upper()}"
            
            # Crear el bin
            bin_data = {
                'codigo': codigo,
                'business': business,
                'producto': producto,
                'proveedor': proveedor,
                'recepcion': recepcion,
                **validated_data
            }
            
            bin_obj = FruitBin.objects.create(**bin_data)
            bins_creados.append(bin_obj)
        
        return bins_creados
