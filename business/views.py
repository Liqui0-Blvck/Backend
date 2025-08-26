from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Business, BusinessConfig
from .serializers import BusinessSerializer, BusinessConfigSerializer
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from django.db.models import Q

class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    
    def get_queryset(self):
        # Un usuario puede ver su empresa asociada en perfil y/o negocios donde es dueño
        user = self.request.user
        if hasattr(user, 'perfil') and user.perfil:
            perfil = user.perfil
            return Business.objects.filter(Q(id=getattr(perfil, 'business_id', None)) | Q(dueno=perfil)).distinct()
        return Business.objects.none()

    # La creación exige 'dueno' explícito desde el serializer; no lo sobreescribimos aquí.


class BusinessConfigViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Cada usuario solo puede ver/editar su propia configuración
        if hasattr(self.request.user, 'perfil'):
            return BusinessConfig.objects.filter(user=self.request.user.perfil)
        return BusinessConfig.objects.none()
    
    @action(detail=False, methods=['GET', 'PUT', 'PATCH'])
    def my_config(self, request):
        """Obtener o actualizar la configuración del usuario actual"""
        if not hasattr(request.user, 'perfil'):
            return Response({"error": "Usuario sin perfil"}, status=status.HTTP_400_BAD_REQUEST)
            
        config, created = BusinessConfig.objects.get_or_create(
            user=request.user.perfil,
            defaults={
                'default_view_mode': 'standard'
            }
        )
        
        if request.method in ['PUT', 'PATCH']:
            # Actualizar la configuración con los datos recibidos
            serializer = self.get_serializer(config, data=request.data, partial=request.method=='PATCH')
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # GET request
            serializer = self.get_serializer(config)
            return Response(serializer.data)
