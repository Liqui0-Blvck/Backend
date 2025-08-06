from rest_framework import serializers
from .models_banking import BankAccount
from .models import Business

class BankAccountSerializer(serializers.ModelSerializer):
    banco_nombre = serializers.SerializerMethodField(read_only=True)
    tipo_cuenta_display = serializers.SerializerMethodField(read_only=True)
    business_nombre = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BankAccount
        fields = '__all__'
    
    def get_banco_nombre(self, obj):
        return obj.banco_nombre
    
    def get_tipo_cuenta_display(self, obj):
        return obj.get_tipo_cuenta_display()
    
    def get_business_nombre(self, obj):
        if obj.business:
            return obj.business.nombre
        return None

class BankAccountNestedSerializer(serializers.ModelSerializer):
    """
    Serializer para incluir cuentas bancarias anidadas en el serializer de Business
    """
    banco_nombre = serializers.SerializerMethodField(read_only=True)
    tipo_cuenta_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BankAccount
        exclude = ('business', 'created_at', 'updated_at')
    
    def get_banco_nombre(self, obj):
        return obj.banco_nombre
    
    def get_tipo_cuenta_display(self, obj):
        return obj.get_tipo_cuenta_display()
