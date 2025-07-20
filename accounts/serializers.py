from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import ConfiguracionUsuario, CustomUser, Perfil
from business.models import Business

class GroupSerializer(serializers.ModelSerializer):
    """Serializador para los grupos de Django que representan roles"""
    
    class Meta:
        model = Group
        fields = ['id', 'name']

class PerfilSerializer(serializers.ModelSerializer):
    business_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Perfil
        fields = ['id', 'phone', 'rut', 'business', 'business_name']
    
    def get_business_name(self, obj):
        if obj.business:
            return obj.business.nombre
        return None

class MePerfilSerializer(serializers.ModelSerializer):
    business_name = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = Perfil
        fields = ['id', 'phone', 'rut', 'business', 'business_name', 'user']
    
    def get_business_name(self, obj):
        if obj.business:
            return obj.business.nombre
        return None
        
    def get_user(self, obj):
        user = obj.user
        if user:
            return {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'second_name': user.second_name,
                'second_last_name': user.second_last_name,
                'roles': [group.name for group in user.groups.all()]
            }
        return None

class CustomUserSerializer(serializers.ModelSerializer):
    perfil = PerfilSerializer(read_only=True)
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'created_at',
            'email',
            'first_name',
            'last_name',
            'second_name',
            'second_last_name',
            'last_login',
            'perfil',
            'roles',
            'is_active'
        ]
    
    def get_roles(self, obj):
        return [group.name for group in obj.groups.all()]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    rut = serializers.CharField(required=False, allow_blank=True)
    business_id = serializers.IntegerField(required=True, write_only=True)
    primary_group = serializers.CharField(required=False, write_only=True)  # Grupo principal
    additional_groups = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )  # Grupos adicionales
    roles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = CustomUser
        fields = [
            'email', 'password', 'first_name', 'last_name', 'second_name', 
            'second_last_name', 'primary_group', 'phone', 'rut', 'business_id', 'additional_groups', 'roles'
        ]
    
    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return value
    
    def validate_rut(self, value):
        if value and Perfil.objects.filter(rut=value).exists():
            raise serializers.ValidationError("Este RUT ya está registrado.")
        return value
    
    def validate(self, data):
        # Permitir que si se envía 'roles', se derive primary_group y additional_groups
        roles = data.get('roles')
        if roles and not data.get('primary_group'):
            data['primary_group'] = roles[0]
            data['additional_groups'] = roles[1:] if len(roles) > 1 else []
        primary_group = data.get('primary_group')
        additional_groups = data.get('additional_groups', [])
        if primary_group in additional_groups:
            raise serializers.ValidationError({"additional_groups": "El grupo principal no puede estar en los grupos adicionales."})
        
        # Verificar que los grupos existan
        all_groups = [primary_group] + additional_groups
        for group_name in all_groups:
            if not Group.objects.filter(name=group_name).exists():
                raise serializers.ValidationError({"primary_group": f"El grupo '{group_name}' no existe."})
        return data
    
    def create(self, validated_data):
        # Permitir compatibilidad: si vienen 'roles', derivar primary_group y additional_groups
        roles = validated_data.pop('roles', None)
        if roles and not validated_data.get('primary_group'):
            validated_data['primary_group'] = roles[0]
            validated_data['additional_groups'] = roles[1:] if len(roles) > 1 else []
        # Extraer datos para el perfil
        phone = validated_data.pop('phone', None)
        rut = validated_data.pop('rut', None)
        business_id = validated_data.pop('business_id')
        
        # Extraer grupos
        primary_group = validated_data.pop('primary_group')
        additional_groups = validated_data.pop('additional_groups', [])
        
        # Crear usuario
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        
        # Asignar grupos
        primary_group_obj = Group.objects.get(name=primary_group)
        user.groups.add(primary_group_obj)
        for group_name in additional_groups:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
        
        # Crear perfil
        from business.models import Business
        business = Business.objects.get(id=business_id)
        Perfil.objects.create(
            user=user,
            phone=phone,
            rut=rut,
            business=business
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False, allow_blank=True, write_only=True)
    rut = serializers.CharField(required=False, allow_blank=True, write_only=True)
    primary_group = serializers.CharField(required=False, write_only=True)  # Grupo principal
    additional_groups = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )  # Grupos adicionales
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'second_name', 'second_last_name',
            'primary_group', 'additional_groups', 'is_active', 'phone', 'rut'
        ]
    
    def validate_rut(self, value):
        # Validar que el RUT no esté en uso por otro usuario
        if value:
            perfil_with_rut = Perfil.objects.filter(rut=value).first()
            if perfil_with_rut and perfil_with_rut.user.id != self.instance.id:
                raise serializers.ValidationError("Este RUT ya está registrado por otro usuario.")
        return value
    
    def validate(self, data):
        # Validar que el grupo principal no esté en los adicionales
        primary_group = data.get('primary_group')
        additional_groups = data.get('additional_groups', [])
        
        if primary_group and primary_group in additional_groups:
            raise serializers.ValidationError({"additional_groups": "El grupo principal no puede estar en los grupos adicionales."})
        
        # Verificar que los grupos existan
        all_groups = []
        if primary_group:
            all_groups.append(primary_group)
        all_groups.extend(additional_groups)
        
        for group_name in all_groups:
            if not Group.objects.filter(name=group_name).exists():
                raise serializers.ValidationError({"primary_group": f"El grupo '{group_name}' no existe."})
        return data
    
    def update(self, instance, validated_data):
        # Extraer datos para el perfil
        phone = validated_data.pop('phone', None)
        rut = validated_data.pop('rut', None)
        
        # Extraer grupos
        primary_group = validated_data.pop('primary_group', None)
        additional_groups = validated_data.pop('additional_groups', None)
        
        # Actualizar usuario
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar grupos si se proporcionaron
        if primary_group is not None:
            # Limpiar grupos existentes
            instance.groups.clear()
            
            # Asignar grupo principal
            primary_group_obj = Group.objects.get(name=primary_group)
            instance.groups.add(primary_group_obj)
            
            # Asignar grupos adicionales
            if additional_groups:
                for group_name in additional_groups:
                    group = Group.objects.get(name=group_name)
                    instance.groups.add(group)
        elif additional_groups is not None:
            # Si solo se proporcionaron grupos adicionales, mantener el grupo principal
            current_groups = list(instance.groups.all())
            if current_groups:
                main_group = current_groups[0]
                instance.groups.clear()
                instance.groups.add(main_group)
                for group_name in additional_groups:
                    group = Group.objects.get(name=group_name)
                    instance.groups.add(group)
        
        # Actualizar perfil
        if hasattr(instance, 'perfil'):
            if phone is not None:
                instance.perfil.phone = phone
            if rut is not None:
                instance.perfil.rut = rut
            instance.perfil.save()
        return instance


class UserConfig(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionUsuario
        fields = '__all__'