from rest_framework import serializers
from .models import Business, BusinessConfig

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = '__all__'

class BusinessConfigSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessConfig
        fields = ('id', 'user', 'user_email', 'default_view_mode')
        
    def get_user_email(self, obj):
        if obj.user and hasattr(obj.user, 'user') and obj.user.user:
            return obj.user.user.email
        return None
