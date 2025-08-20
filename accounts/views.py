from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from django.contrib.auth import authenticate
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.models import Group
from django.utils import timezone

from .models import ConfiguracionUsuario, CustomUser, Perfil
from .serializers import (
    CustomUserSerializer, PerfilSerializer, GroupSerializer, UserConfig,
    UserCreateSerializer, UserUpdateSerializer, MePerfilSerializer
)
from core.permissions import IsSameBusiness

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'detail': 'CSRF cookie set'})

class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    filter_backends = [filters.SearchFilter]
    search_fields = ['email', 'first_name', 'last_name']
    
    def get_queryset(self):
        # Accedemos al business a través del perfil del usuario
        if not hasattr(self.request.user, 'perfil') or not self.request.user.perfil.business:
            return CustomUser.objects.none()
        
        # Filtramos usuarios que pertenecen al mismo negocio
        return CustomUser.objects.filter(
            perfil__business=self.request.user.perfil.business
        ).order_by('first_name', 'last_name')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return CustomUserSerializer
    
    def get_permissions(self):
        # Permitir a vendedores crear usuarios si el grupo solicitado es Cliente
        if self.action == 'create':
            from core.permissions import IsAdminOrOwner, IsSupervisor
            request = self.request
            # Intentar obtener el grupo solicitado del payload
            data = request.data
            grupo_cliente = False
            # Permitir tanto 'roles' como 'primary_group' en el payload
            if 'roles' in data and data['roles']:
                grupo_cliente = data['roles'][0].lower() == 'cliente'
            elif 'primary_group' in data:
                grupo_cliente = data['primary_group'].lower() == 'cliente'
            if grupo_cliente:
                # Permitir a administradores, supervisores y vendedores crear clientes
                from rest_framework.permissions import OR
                self.permission_classes = [IsAuthenticated, OR(IsAdminOrOwner, IsSupervisor)]
                return super().get_permissions()
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from core.permissions import IsAdminOrOwner
            self.permission_classes = [IsAuthenticated, IsAdminOrOwner]
        return super().get_permissions()
        
    def retrieve(self, request, *args, **kwargs):
        """Sobreescribir retrieve para incluir información de roles más clara"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Agregar información de roles
        data = self._add_roles_info(instance, data)
            
        return Response(data)
        
    def list(self, request, *args, **kwargs):
        """Sobreescribir list para incluir información de roles en todos los usuarios"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            
            # Agregar información de roles a cada usuario
            for i, user in enumerate(page):
                data[i] = self._add_roles_info(user, data[i])
                
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        
        # Agregar información de roles a cada usuario
        for i, user in enumerate(queryset):
            data[i] = self._add_roles_info(user, data[i])
            
        return Response(data)
    
    def _add_roles_info(self, user_instance, user_data):
        """Método auxiliar para agregar información esencial de roles a los datos de un usuario"""
        # Obtener todos los grupos/roles del usuario
        groups = user_instance.groups.all()
        
        # Lista simple de nombres de roles
        user_data['roles'] = [group.name for group in groups]
        
        # Estructura de roles principal y adicionales
        if groups.exists():
            # El primer grupo es el rol principal
            primary_group = groups.first()
            primary_role = {
                'id': primary_group.id,
                'name': primary_group.name
            }
            
            # Los demás grupos son roles adicionales
            additional_roles = [{
                'id': group.id,
                'name': group.name
            } for group in groups.exclude(id=primary_group.id)]
            
            user_data['roles_info'] = {
                'primary_role': primary_role,
                'additional_roles': additional_roles
            }
        else:
            user_data['roles_info'] = {
                'primary_role': None,
                'additional_roles': []
            }
            
        return user_data
    
    @action(detail=True, methods=['post'], url_path='add-role')
    def add_role(self, request, pk=None):
        """Agregar un rol adicional a un usuario usando grupos de Django"""
        user = self.get_object()
        role_name = request.data.get('role')
        
        if not role_name:
            return Response({'detail': 'Se requiere especificar un rol.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que el grupo exista
        try:
            group = Group.objects.get(name=role_name)
        except Group.DoesNotExist:
            return Response({'detail': f'Rol inválido. El grupo {role_name} no existe.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que no sea el rol principal (primer grupo)
        if user.groups.exists() and user.groups.first().name == role_name:
            return Response({'detail': 'Este rol ya es el rol principal del usuario.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que no tenga ya este rol
        if user.groups.filter(name=role_name).exists():
            return Response({'detail': 'El usuario ya tiene este rol asignado.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Asignar el rol (grupo) al usuario
        user.groups.add(group)
        
        # Devolver la información del grupo asignado
        serializer = GroupSerializer(group)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'], url_path='remove-role/(?P<role_id>[^/.]+)')
    def remove_role(self, request, pk=None, role_id=None):
        """Eliminar un rol adicional de un usuario usando grupos de Django"""
        user = self.get_object()
        
        try:
            # Ahora role_id es el ID del grupo
            group = Group.objects.get(id=role_id)
        except Group.DoesNotExist:
            return Response({'detail': 'Rol no encontrado.'}, 
                            status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que el usuario tenga este grupo
        if not user.groups.filter(id=role_id).exists():
            return Response({'detail': 'El usuario no tiene este rol asignado.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que no sea el rol principal (primer grupo)
        if user.groups.first().id == int(role_id):
            return Response({'detail': 'No se puede eliminar el rol principal. Use la actualización de usuario para cambiarlo.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Eliminar el grupo del usuario
        user.groups.remove(group)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], url_path='roles')
    def get_roles(self, request, pk=None):
        """Obtener todos los roles de un usuario usando grupos de Django"""
        user = self.get_object()
        groups = user.groups.all()
        
        if not groups.exists():
            return Response({
                'primary_role': None,
                'additional_roles': []
            })
        
        # El primer grupo es el rol principal
        primary_group = groups.first()
        primary_serializer = GroupSerializer(primary_group)
        
        # Los demás grupos son roles adicionales
        additional_groups = groups.exclude(id=primary_group.id)
        additional_serializer = GroupSerializer(additional_groups, many=True)
        
        response_data = {
            'primary_role': primary_serializer.data,
            'additional_roles': additional_serializer.data
        }
        
        return Response(response_data)



class LoginView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({'detail': 'Email and password required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if not user.is_active:
                return Response({'detail': 'User inactive.'}, status=status.HTTP_403_FORBIDDEN)
            refresh = RefreshToken.for_user(user)
            perfil = getattr(user, 'perfil', None)
            perfil_data = PerfilSerializer(perfil).data if perfil else None
            response = Response({
                'detail': 'Login successful.',
                'user': perfil_data
            })
            response.set_cookie(
                key='accessToken',
                value=str(refresh.access_token),
                httponly=True,
                secure=False,  # Cambia a False para desarrollo local si no usas HTTPS
                samesite='Lax',
                max_age=3600,
                path='/'
            )
            response.set_cookie(
                key='refreshToken',
                value=str(refresh),
                httponly=True,
                secure=False,
                samesite='Lax',
                max_age=7*24*3600,
                path='/'
            )
            return response
        return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)



class RefreshView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get('refreshToken')
        if not refresh_token:
            return Response({'detail': 'No refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
        except TokenError:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
        response = Response({'detail': 'Token refreshed.'})
        response.set_cookie(
            key='accessToken',
            value=access_token,
            httponly=True,
            secure=False,  # Cambia a False para dev local
            samesite='Lax',
            max_age=3600,
            path='/'
        )
        return response


from .authentication import CustomJWTAuthentication

class MeView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
            
        # Obtener o crear la configuración del negocio
        from business.models import BusinessConfig
        from business.serializers import BusinessConfigSerializer
        
        # Manejar el caso donde existen múltiples configuraciones
        business_configs = BusinessConfig.objects.filter(user=perfil)
        
        if business_configs.exists():
            # Si hay múltiples configuraciones, usar la primera
            config = business_configs.first()
            created = False
            
            # Si hay más de una configuración, registrar un mensaje de advertencia
            if business_configs.count() > 1:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Multiple BusinessConfig objects found for user {perfil.id}. Using the first one.")
        else:
            # Si no existe ninguna configuración, crearla
            config = BusinessConfig.objects.create(
                user=perfil,
                default_view_mode='standard'
            )
            created = True
        
        # Obtener o crear la configuración del usuario
        from .models import ConfiguracionUsuario
        from .serializers import UserConfig
        
        user_config, created = ConfiguracionUsuario.objects.get_or_create(
            perfil=perfil,
            defaults={
                'notificaciones': True,
                'privacidad': True,
                'estilo_aplicacion': 'light',
                'color_aplicacion': 'white'
            }
        )
        
        # Serializar el perfil y las configuraciones
        perfil_serializer = MePerfilSerializer(perfil)
        config_serializer = BusinessConfigSerializer(config)
        user_config_serializer = UserConfig(user_config)
        
        # Combinar los datos en una sola respuesta
        response_data = perfil_serializer.data
        response_data['config'] = config_serializer.data
        response_data['user_config'] = user_config_serializer.data
        
        return Response(response_data)

class LogoutView(APIView):
    permission_classes = []
    authentication_classes = []
    def post(self, request):
        response = Response({'detail': 'Logged out.'})
        response.delete_cookie('accessToken', path='/')
        response.delete_cookie('refreshToken', path='/')
        return response


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        # Validar que se proporcionaron todos los campos necesarios
        if not current_password or not new_password or not confirm_password:
            return Response(
                {'error': 'Se requieren contraseña actual, nueva contraseña y confirmación.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que la contraseña actual es correcta
        if not user.check_password(current_password):
            return Response(
                {'error': 'La contraseña actual es incorrecta.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que las nuevas contraseñas coinciden
        if new_password != confirm_password:
            return Response(
                {'error': 'La nueva contraseña y su confirmación no coinciden.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que la nueva contraseña cumple con los requisitos mínimos
        if len(new_password) < 8:
            return Response(
                {'error': 'La nueva contraseña debe tener al menos 8 caracteres.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar la contraseña
        user.set_password(new_password)
        user.save()
        
        # Actualizar los tokens para mantener la sesión activa
        refresh = RefreshToken.for_user(user)
        
        response = Response({
            'detail': 'Contraseña actualizada con éxito.',
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        })
        
        # Actualizar las cookies con los nuevos tokens
        response.set_cookie(
            key='accessToken',
            value=str(refresh.access_token),
            httponly=True,
            secure=False,  # Cambia a True en producción con HTTPS
            samesite='Lax',
            max_age=3600,
            path='/'
        )
        response.set_cookie(
            key='refreshToken',
            value=str(refresh),
            httponly=True,
            secure=False,  # Cambia a True en producción con HTTPS
            samesite='Lax',
            max_age=86400 * 7,  # 7 días
            path='/'
        )
        
        return response


class ConfiguracionUsuarioViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionUsuario.objects.all()
    serializer_class = UserConfig
    
    def get_queryset(self):
        return ConfiguracionUsuario.objects.filter(perfil=self.request.user.perfil)
    
    def get_object(self):
        return ConfiguracionUsuario.objects.get(perfil=self.request.user.perfil)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
            