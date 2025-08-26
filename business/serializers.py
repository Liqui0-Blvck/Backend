from rest_framework import serializers
from .models import Business, BusinessConfig
from accounts.models import Perfil
from .serializers_banking import BankAccountNestedSerializer

class BusinessSerializer(serializers.ModelSerializer):
    bank_accounts = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Business
        fields = '__all__'
    
    def get_bank_accounts(self, obj):
        """Devuelve las cuentas bancarias activas del negocio"""
        accounts = obj.bank_accounts.filter(activa=True).order_by('orden')
        return BankAccountNestedSerializer(accounts, many=True).data

    def create(self, validated_data):
        """Requiere que 'dueno' venga explícitamente en el payload."""
        if 'dueno' not in validated_data or validated_data.get('dueno') is None:
            raise serializers.ValidationError({'dueno': 'Debes especificar el dueño (Perfil) del negocio.'})
        return super().create(validated_data)

class BusinessConfigSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessConfig
        fields = ('id', 'user', 'user_email', 'default_view_mode')
        
    def get_user_email(self, obj):
        if obj.user and hasattr(obj.user, 'user') and obj.user.user:
            return obj.user.user.email
        return None
