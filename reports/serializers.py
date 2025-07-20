from rest_framework import serializers

class BaseProductReportSerializer(serializers.Serializer):
    """Serializador base para reportes de productos"""
    id = serializers.IntegerField()
    producto_id = serializers.IntegerField()
    producto_nombre = serializers.CharField()
    total_lotes = serializers.IntegerField()
    peso_total = serializers.FloatField()
    peso_disponible = serializers.FloatField()
    valor_total = serializers.FloatField()

class PaltaReportSerializer(BaseProductReportSerializer):
    """Serializador especializado para reportes de paltas"""
    distribucion_maduracion = serializers.DictField()
    perdida_estimada = serializers.DictField()
    precio_promedio = serializers.FloatField()
    margen_promedio = serializers.FloatField()
    peso_vendible = serializers.FloatField()
    ingreso_estimado = serializers.FloatField()
    ganancia_estimada = serializers.FloatField()
    calibres_disponibles = serializers.ListField(child=serializers.CharField())
    
    # Campos específicos para paltas
    dias_promedio_maduracion = serializers.FloatField(required=False)
    porcentaje_maduracion = serializers.DictField(required=False)

class MangoReportSerializer(BaseProductReportSerializer):
    """Serializador especializado para reportes de mangos"""
    total_cajas = serializers.IntegerField()
    costo_por_caja = serializers.FloatField()
    precio_recomendado_caja = serializers.FloatField(required=False)
    mangos_por_caja = serializers.IntegerField(required=False)
    peso_por_mango = serializers.FloatField(required=False)
    calibres_disponibles = serializers.ListField(child=serializers.CharField())

class PlatanoReportSerializer(BaseProductReportSerializer):
    """Serializador especializado para reportes de plátanos"""
    total_cajas = serializers.IntegerField()
    costo_por_caja = serializers.FloatField()
    precio_recomendado_caja = serializers.FloatField(required=False)
    peso_por_caja = serializers.FloatField(required=False)
    calibres_disponibles = serializers.ListField(child=serializers.CharField())

class StockReportResponseSerializer(serializers.Serializer):
    """Serializador para la respuesta completa del reporte de stock"""
    periodo = serializers.DictField()
    filtros_aplicados = serializers.DictField()
    total_productos = serializers.IntegerField()
    total_lotes = serializers.IntegerField()
    lotes = serializers.ListField(child=serializers.DictField())
    resumen_por_producto = serializers.ListField(child=serializers.DictField())
    
    # Campos opcionales según el tipo de producto
    detalle_producto = serializers.DictField(required=False)
    resumen_general_paltas = serializers.DictField(required=False)
    recomendaciones_paltas = serializers.ListField(child=serializers.DictField(), required=False)
    resumen_paltas_por_calibre = serializers.ListField(child=serializers.DictField(), required=False)
    totales_paltas = serializers.DictField(required=False)
    totales_otros = serializers.DictField(required=False)
