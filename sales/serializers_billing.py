from rest_framework import serializers
from .models_billing import BillingInfo
from .models import Customer

class BillingInfoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BillingInfo
        fields = '__all__'
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return None

class BillingInfoNestedSerializer(serializers.ModelSerializer):
    """
    Serializer para incluir información de facturación anidada en el serializer de Cliente
    """
    class Meta:
        model = BillingInfo
        exclude = ('cliente', 'created_at', 'updated_at')
