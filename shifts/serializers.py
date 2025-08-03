from rest_framework import serializers
from .models import Shift, BoxRefill, ShiftExpense

class ShiftSerializer(serializers.ModelSerializer):
    usuario_abre_nombre = serializers.SerializerMethodField()
    usuario_cierra_nombre = serializers.SerializerMethodField()
    duracion_minutos = serializers.SerializerMethodField()
    
    class Meta:
        model = Shift
        fields = '__all__'
    
    def get_usuario_abre_nombre(self, obj):
        if obj.usuario_abre:
            return f"{obj.usuario_abre.first_name} {obj.usuario_abre.last_name}".strip() or obj.usuario_abre.username
        return None
    
    def get_usuario_cierra_nombre(self, obj):
        if obj.usuario_cierra:
            return f"{obj.usuario_cierra.first_name} {obj.usuario_cierra.last_name}".strip() or obj.usuario_cierra.username
        return None
    
    def get_duracion_minutos(self, obj):
        if obj.fecha_apertura and obj.fecha_cierre:
            # Calcular la duración en minutos
            delta = obj.fecha_cierre - obj.fecha_apertura
            return int(delta.total_seconds() / 60)
        return None


class ShiftExpenseSerializer(serializers.ModelSerializer):
    """Serializador para los gastos incurridos durante un turno"""
    autorizado_por_nombre = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()
    categoria_display = serializers.SerializerMethodField()
    metodo_pago_display = serializers.SerializerMethodField()
    comprobante_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ShiftExpense
        fields = [
            'id', 'shift', 'descripcion', 'monto', 'categoria', 'categoria_display',
            'metodo_pago', 'metodo_pago_display', 'comprobante', 'comprobante_url',
            'numero_comprobante', 'proveedor', 'autorizado_por', 'autorizado_por_nombre',
            'registrado_por', 'registrado_por_nombre', 'fecha', 'notas', 'business'
        ]
    
    def get_autorizado_por_nombre(self, obj):
        if obj.autorizado_por:
            return f"{obj.autorizado_por.first_name} {obj.autorizado_por.last_name}".strip() or obj.autorizado_por.username
        return None
    
    def get_registrado_por_nombre(self, obj):
        if obj.registrado_por:
            return f"{obj.registrado_por.first_name} {obj.registrado_por.last_name}".strip() or obj.registrado_por.username
        return None
    
    def get_categoria_display(self, obj):
        return obj.get_categoria_display()
    
    def get_metodo_pago_display(self, obj):
        return obj.get_metodo_pago_display()
    
    def get_comprobante_url(self, obj):
        if obj.comprobante:
            return obj.comprobante.url
        return None
