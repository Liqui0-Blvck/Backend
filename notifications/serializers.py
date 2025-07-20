from rest_framework import serializers
from .models import Notification, WebhookSubscription
from .utils import get_user_role

class NotificationSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de notificaciones"""
    emisor_id = serializers.ReadOnlyField(source='emisor.id')
    emisor_rol = serializers.SerializerMethodField()
    emisor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id',
            'uid',
            'usuario',
            'emisor_id',
            'emisor_rol',
            'emisor_nombre',
            'titulo',
            'mensaje',
            'tipo',
            'leida',
            'fecha_lectura',
            'enlace',
            'objeto_relacionado_tipo',
            'objeto_relacionado_id',
            'created_at',
        )
        read_only_fields = ('created_at', 'uid')

    def get_emisor_rol(self, obj):
        if obj.emisor:
            return get_user_role(obj.emisor)
        return None

    def get_emisor_nombre(self, obj):
        if obj.emisor:
            return obj.emisor.get_full_name() or obj.emisor.email
        return "Sistema"

class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de suscripciones a webhooks."""
    class Meta:
        model = WebhookSubscription
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de notificaciones"""
    emisor_id = serializers.ReadOnlyField(source='emisor.id')
    emisor_rol = serializers.SerializerMethodField()
    emisor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'uid', 'usuario', 'titulo', 'mensaje', 'tipo', 'leida', 
            'fecha_lectura', 'enlace', 'objeto_relacionado_tipo', 
            'objeto_relacionado_id', 'created_at', 'updated_at',
            'emisor_id',
            'emisor_rol',
            'emisor_nombre',
        ]
        read_only_fields = ['id', 'uid', 'created_at', 'updated_at']

    def get_emisor_rol(self, obj):
        """Obtiene el rol del emisor desde el campo emisor del objeto."""
        emisor = obj.emisor
        if not emisor:
            return None
        
        if emisor.is_superuser:
            return 'superuser'
        
        # El rol se obtiene del primer grupo al que pertenece el usuario
        grupo = emisor.groups.first()
        if grupo:
            return grupo.name
            
        return 'usuario' # Rol por defecto si no tiene grupo

    def get_emisor_nombre(self, obj):
        if obj.emisor:
            return obj.emisor.get_full_name() or obj.emisor.email
        return 'Sistema'


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de suscripción a webhooks"""
    business_name = serializers.SerializerMethodField()
    
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
