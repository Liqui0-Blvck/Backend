from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import ConfiguracionUsuario, CustomUser, Perfil
from business.models import Business
from inventory.models import Supplier

class GroupSerializer(serializers.ModelSerializer):
    """Serializador para los grupos de Django que representan roles"""
    
    class Meta:
        model = Group
        fields = ['id', 'name']

class PerfilSerializer(serializers.ModelSerializer):
    business_name = serializers.SerializerMethodField()
    proveedor_uid = serializers.SerializerMethodField()
    proveedor_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = Perfil
        fields = ['id', 'phone', 'rut', 'business', 'business_name', 'proveedor_uid', 'proveedor_nombre']
    
    def get_business_name(self, obj):
        if obj.business:
            return obj.business.nombre
        return None
    
    def get_proveedor_uid(self, obj):
        return str(obj.proveedor.uid) if getattr(obj, 'proveedor', None) else None
    
    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if getattr(obj, 'proveedor', None) else None

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
    # Vínculo con proveedor existente (opcional, requerido si rol=Proveedor)
    # proveedor_id = serializers.IntegerField(required=False, write_only=True)
    proveedor_uid = serializers.CharField(required=False, write_only=True)
    proveedor_rut = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'email', 'password', 'first_name', 'last_name', 'second_name', 
            'second_last_name', 'primary_group', 'phone', 'rut', 'business_id', 'additional_groups', 'roles',
            'proveedor_uid', 'proveedor_rut'
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

        # Resolver proveedor si fue enviado (soportar formato anidado en perfil)
        proveedor_id = data.get('proveedor_id') if 'proveedor_id' in self.fields else None
        proveedor_uid = data.get('proveedor_uid')
        proveedor_rut = data.get('proveedor_rut')

        # Si no viene en nivel raíz, intentar leer de payload original: perfil.proveedor / perfil.proveedor_uid / perfil.proveedor_rut
        if not any([proveedor_id, proveedor_uid, proveedor_rut]):
            initial = getattr(self, 'initial_data', {}) or {}
            perfil_payload = initial.get('perfil') or {}
            # permitir clave única 'proveedor' (asumimos UID), o claves explícitas
            nested_uid = perfil_payload.get('proveedor_uid') or perfil_payload.get('proveedor')
            nested_rut = perfil_payload.get('proveedor_rut')
            nested_id = perfil_payload.get('proveedor_id')
            if nested_uid:
                proveedor_uid = nested_uid
                data['proveedor_uid'] = proveedor_uid
            if nested_rut:
                proveedor_rut = nested_rut
                data['proveedor_rut'] = proveedor_rut
            if nested_id is not None and 'proveedor_id' in self.fields:
                proveedor_id = nested_id
                data['proveedor_id'] = proveedor_id

        business_id = data.get('business_id')

        supplier = None
        provided_supplier = any([proveedor_id, proveedor_uid, proveedor_rut])
        if provided_supplier:
            try:
                if proveedor_id:
                    supplier = Supplier.objects.get(id=proveedor_id)
                elif proveedor_uid:
                    supplier = Supplier.objects.get(uid=proveedor_uid)
                elif proveedor_rut:
                    supplier = Supplier.objects.get(rut=proveedor_rut)
            except Supplier.DoesNotExist:
                raise serializers.ValidationError({"proveedor": "Proveedor no encontrado."})
            # Validar business consistente
            try:
                business = Business.objects.get(id=business_id)
            except Business.DoesNotExist:
                raise serializers.ValidationError({"business_id": "Business no existe."})
            if supplier.business_id != business.id:
                raise serializers.ValidationError({"proveedor": "El proveedor pertenece a otro negocio."})
            # Enforce one user per supplier
            existing = Perfil.objects.filter(proveedor=supplier).first()
            if existing is not None:
                raise serializers.ValidationError({"proveedor": "Ya existe un usuario vinculado a este proveedor."})
            # Adjuntar supplier resuelto para create()
            data['__supplier_obj__'] = supplier

        # Si el rol principal es Proveedor, exigir proveedor
        if primary_group == 'Proveedor' or (roles and 'Proveedor' in roles):
            if not provided_supplier:
                raise serializers.ValidationError({"proveedor": "Debe indicar proveedor (id, uid o rut) para usuarios Proveedor."})
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
        supplier = validated_data.pop('__supplier_obj__', None)
        # Quitar campos no pertenecientes al modelo CustomUser
        validated_data.pop('proveedor_uid', None)
        validated_data.pop('proveedor_rut', None)
        validated_data.pop('proveedor_id', None)
        
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
        perfil = Perfil.objects.create(
            user=user,
            phone=phone,
            rut=rut,
            business=business
        )
        if supplier:
            perfil.proveedor = supplier
            perfil.save(update_fields=['proveedor'])
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
    # Cambiar vínculo con proveedor
    proveedor_id = serializers.IntegerField(required=False, write_only=True)
    proveedor_uid = serializers.CharField(required=False, write_only=True)
    proveedor_rut = serializers.CharField(required=False, write_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'second_name', 'second_last_name',
            'primary_group', 'additional_groups', 'is_active', 'phone', 'rut',
            'proveedor_id', 'proveedor_uid', 'proveedor_rut'
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

        # Resolver proveedor si fue enviado (soportar formato anidado en perfil)
        proveedor_id = data.get('proveedor_id') if 'proveedor_id' in self.fields else None
        proveedor_uid = data.get('proveedor_uid')
        proveedor_rut = data.get('proveedor_rut')
        if not any([proveedor_id, proveedor_uid, proveedor_rut]):
            initial = getattr(self, 'initial_data', {}) or {}
            perfil_payload = initial.get('perfil') or {}
            nested_uid = perfil_payload.get('proveedor_uid') or perfil_payload.get('proveedor')
            nested_rut = perfil_payload.get('proveedor_rut')
            nested_id = perfil_payload.get('proveedor_id')
            if nested_uid:
                proveedor_uid = nested_uid
                data['proveedor_uid'] = proveedor_uid
            if nested_rut:
                proveedor_rut = nested_rut
                data['proveedor_rut'] = proveedor_rut
            if nested_id is not None and 'proveedor_id' in self.fields:
                proveedor_id = nested_id
                data['proveedor_id'] = proveedor_id

        supplier = None
        if any([proveedor_id, proveedor_uid, proveedor_rut]):
            try:
                if proveedor_id:
                    supplier = Supplier.objects.get(id=proveedor_id)
                elif proveedor_uid:
                    supplier = Supplier.objects.get(uid=proveedor_uid)
                elif proveedor_rut:
                    supplier = Supplier.objects.get(rut=proveedor_rut)
            except Supplier.DoesNotExist:
                raise serializers.ValidationError({"proveedor": "Proveedor no encontrado."})
            # Validar que el supplier pertenezca al mismo business del perfil
            perfil = getattr(self.instance, 'perfil', None)
            if not perfil or not (perfil.business or perfil.proveedor):
                # Si no tenemos business en perfil, permitir, se validará en update por permisos
                pass
            else:
                expected_business_id = perfil.business_id or (perfil.proveedor.business_id if perfil.proveedor else None)
                if expected_business_id and supplier.business_id != expected_business_id:
                    raise serializers.ValidationError({"proveedor": "El proveedor pertenece a otro negocio."})
            # Enforce one user per supplier (allow same user)
            existing = Perfil.objects.filter(proveedor=supplier).first()
            if existing is not None and existing.user_id != self.instance.id:
                raise serializers.ValidationError({"proveedor": "Ya existe un usuario vinculado a este proveedor."})
            data['__supplier_obj__'] = supplier
        return data
    
    def update(self, instance, validated_data):
        # Extraer datos para el perfil
        phone = validated_data.pop('phone', None)
        rut = validated_data.pop('rut', None)
        supplier = validated_data.pop('__supplier_obj__', None)
        # Quitar campos no pertenecientes al modelo CustomUser
        validated_data.pop('proveedor_uid', None)
        validated_data.pop('proveedor_rut', None)
        validated_data.pop('proveedor_id', None)
        
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
            if supplier is not None:
                instance.perfil.proveedor = supplier
            instance.perfil.save()
        return instance


class UserConfig(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionUsuario
        fields = '__all__'