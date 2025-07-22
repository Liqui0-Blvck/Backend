from rest_framework import serializers
from .models import Notification, WebhookSubscription
from accounts.models import CustomUser

# Serializador simple para mostrar información básica del usuario
class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name']

class NotificationSerializer(serializers.ModelSerializer):
    """Serializador unificado y corregido para el modelo de notificaciones."""
    usuario = UserSimpleSerializer(read_only=True)
    emisor = UserSimpleSerializer(read_only=True)
    emisor_id = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), source='emisor', write_only=True, allow_null=True)
    usuario_id = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), source='usuario', write_only=True)

    class Meta:
        model = Notification
        fields = (
            'id', 'uid', 'usuario', 'emisor', 'titulo', 'mensaje', 'tipo',
            'leida', 'fecha_lectura', 'enlace', 'objeto_relacionado_tipo',
            'objeto_relacionado_id', 'created_at', 'emisor_id', 'usuario_id'
        )
        read_only_fields = ('id', 'uid', 'created_at', 'usuario', 'emisor')

class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de suscripción a webhooks"""
    business_name = serializers.CharField(source='business.name', read_only=True)
    
    class Meta:
        model = WebhookSubscription
        fields = ['id', 'business', 'business_name', 'url', 'secret_key', 'is_active',
                 'anuncios', 'inventario', 'ventas', 'turnos', 'created_at', 'updated_at']
        read_only_fields = ['id', 'business', 'created_at', 'updated_at']
        extra_kwargs = {
            'secret_key': {'write_only': True}
        }
    
    def get_business_name(self, obj):
        return obj.business.nombre if obj.business else None
