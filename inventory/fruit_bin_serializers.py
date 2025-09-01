from rest_framework import serializers
from .models import FruitBin, ReceptionDetail, Product, Supplier, GoodsReception
from .bin_to_lot_models import BinToLotTransformationDetail
from .serializers import ProductSerializer
import uuid
from django.shortcuts import get_object_or_404

class FruitBinListSerializer(serializers.ModelSerializer):
    """Serializador para listar bins de fruta con información resumida"""
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_tipo = serializers.CharField(source='producto.tipo_producto', read_only=True)
    producto = serializers.UUIDField(source='producto.uid', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    proveedor = serializers.UUIDField(source='proveedor.uid', read_only=True)
    recepcion = serializers.UUIDField(source='recepcion.uid', read_only=True, allow_null=True)
    peso_neto = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    calidad_display = serializers.CharField(source='get_calidad_display', read_only=True)
    
    class Meta:
        model = FruitBin
        fields = [
            'uid', 'codigo', 'producto', 'producto_nombre', 'producto_tipo', 'variedad',
            'peso_bruto', 'peso_tara', 'peso_neto', 'estado', 'estado_display',
            'calidad', 'calidad_display', 'proveedor', 'proveedor_nombre', 
            'recepcion', 'fecha_recepcion'
        ]
    
    def get_peso_neto(self, obj):
        return obj.peso_neto


class FruitBinDetailSerializer(serializers.ModelSerializer):
    """Serializador detallado para bins de fruta con toda la información"""
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_tipo = serializers.CharField(source='producto.tipo_producto', read_only=True)
    producto_uid = serializers.UUIDField(source='producto.uid', read_only=True)
    producto_info = ProductSerializer(source='producto', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    proveedor_uid = serializers.UUIDField(source='proveedor.uid', read_only=True, allow_null=True)
    proveedor_info = serializers.SerializerMethodField()
    recepcion_uid = serializers.UUIDField(source='recepcion.uid', read_only=True, allow_null=True)
    peso_neto = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    calidad_display = serializers.CharField(source='get_calidad_display', read_only=True)
    recepcion_info = serializers.SerializerMethodField()
    transformaciones = serializers.SerializerMethodField()
    vendido = serializers.SerializerMethodField()
    venta = serializers.SerializerMethodField()
    
    class Meta:
        model = FruitBin
        fields = [
            'uid', 'codigo', 'producto', 'producto_uid', 'producto_nombre', 'producto_tipo', 'producto_info', 'variedad',
            'peso_bruto', 'peso_tara', 'peso_neto', 'estado', 'estado_display',
            'calidad', 'calidad_display', 'ubicacion', 'recepcion', 'recepcion_uid', 'recepcion_info', 'fecha_recepcion',
            'proveedor', 'proveedor_uid', 'proveedor_nombre', 'proveedor_info', 'temperatura', 'observaciones',
            'created_at', 'updated_at', 'vendido', 'venta', 'transformaciones'
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

    def get_transformaciones(self, obj):
        """Devuelve un resumen de transformaciones Bin -> Lote (pallet) para trazabilidad."""
        try:
            detalles = (
                BinToLotTransformationDetail.objects
                .select_related('transformacion', 'bin', 'transformacion__lote')
                .filter(bin=obj)
                .order_by('-transformacion__fecha_transformacion')[:5]
            )
            data = []
            for d in detalles:
                t = d.transformacion
                data.append({
                    'transformacion_uid': getattr(t, 'uid', None),
                    'fecha_transformacion': getattr(t, 'fecha_transformacion', None),
                    'lote_uid': getattr(getattr(t, 'lote', None), 'uid', None),
                    'kg_descontados': d.kg_descontados,
                    'peso_bruto_previo': d.peso_bruto_previo,
                    'peso_tara_previa': d.peso_tara_previa,
                })
            return data
        except Exception:
            return []

    def get_vendido(self, obj):
        """Retorna True si el bin está vendido, basado en su estado."""
        return obj.estado == 'VENDIDO'

    def get_venta(self, obj):
        """Si el bin fue vendido, retorna información de la venta asociada más reciente."""
        # Solo intentar si está marcado como vendido o si hay relación
        try:
            from sales.models import SaleItem
            si = (
                SaleItem.objects
                .select_related('venta', 'venta__cliente', 'venta__vendedor')
                .filter(bin=obj)
                .order_by('-created_at')
                .first()
            )
            if not si or not si.venta:
                return None
            venta = si.venta
            data = {
                'venta_uid': getattr(venta, 'uid', None),
                'codigo_venta': getattr(venta, 'codigo_venta', None),
                'fecha': getattr(venta, 'created_at', None),
                'total': getattr(venta, 'total', None),
                'metodo_pago': getattr(venta, 'metodo_pago', None),
                'estado_pago': getattr(venta, 'estado_pago', None),
                'cancelada': getattr(venta, 'cancelada', None),
                'cliente': None,
                'vendedor': None,
                'item': {
                    'peso_vendido': getattr(si, 'peso_vendido', None),
                    'unidades_vendidas': getattr(si, 'unidades_vendidas', None),
                    'subtotal': getattr(si, 'subtotal', None),
                    'uid': getattr(si, 'uid', None),
                }
            }
            cliente = getattr(venta, 'cliente', None)
            if cliente:
                data['cliente'] = {
                    'uid': getattr(cliente, 'uid', None),
                    'nombre': getattr(cliente, 'nombre', None),
                    'rut': getattr(cliente, 'rut', None),
                    'telefono': getattr(cliente, 'telefono', None),
                }
            vendedor = getattr(venta, 'vendedor', None)
            if vendedor:
                data['vendedor'] = {
                    'uid': getattr(vendedor, 'uid', None),
                    'nombre': getattr(vendedor, 'full_name', None) or getattr(vendedor, 'username', None),
                }
            return data
        except Exception:
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
