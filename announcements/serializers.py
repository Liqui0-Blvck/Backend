from rest_framework import serializers
from .models import Announcement, AnnouncementConfirmation

class AnnouncementConfirmationSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = AnnouncementConfirmation
        fields = ['id', 'usuario', 'usuario_nombre', 'fecha_confirmacion', 'comentario']
    
    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return f"{obj.usuario.first_name} {obj.usuario.last_name}".strip() or obj.usuario.username
        return None

class AnnouncementSerializer(serializers.ModelSerializer):
    creador_nombre = serializers.SerializerMethodField()
    tipo_display = serializers.SerializerMethodField()
    estado_display = serializers.SerializerMethodField()
    confirmaciones_count = serializers.SerializerMethodField()
    confirmado_por_usuario = serializers.SerializerMethodField()
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'uid', 'business', 'creador', 'creador_nombre', 'titulo', 
            'contenido', 'tipo', 'tipo_display', 'estado', 'estado_display', 
            'fecha_inicio', 'fecha_fin', 'destacado', 'requiere_confirmacion',
            'confirmaciones_count', 'confirmado_por_usuario', 'created_at', 'updated_at'
        ]
    
    def get_creador_nombre(self, obj):
        if obj.creador:
            return f"{obj.creador.first_name} {obj.creador.last_name}".strip() or obj.creador.username
        return None
    
    def get_tipo_display(self, obj):
        return obj.get_tipo_display()
    
    def get_estado_display(self, obj):
        return obj.get_estado_display()
    
    def get_confirmaciones_count(self, obj):
        return obj.confirmaciones.count()
    
    def get_confirmado_por_usuario(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return obj.confirmaciones.filter(usuario=request.user).exists()
        return False

class AnnouncementDetailSerializer(AnnouncementSerializer):
    confirmaciones = AnnouncementConfirmationSerializer(many=True, read_only=True)
    
    class Meta(AnnouncementSerializer.Meta):
        fields = AnnouncementSerializer.Meta.fields + ['confirmaciones']
