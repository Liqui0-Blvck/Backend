from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import FruitBin
from .fruit_bin_serializers import FruitBinListSerializer, FruitBinDetailSerializer, FruitBinBulkCreateSerializer
from core.permissions import IsSameBusiness
from accounts.models import CustomUser, Perfil


class FruitBinViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar bins de fruta.
    Permite listar, crear, actualizar y eliminar bins.
    """
    permission_classes = [IsAuthenticated, IsSameBusiness]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'producto__nombre', 'variedad', 'proveedor__nombre']
    ordering_fields = ['fecha_recepcion', 'codigo', 'peso_bruto']
    ordering = ['-fecha_recepcion']
    lookup_field = 'uid'
    
    def get_queryset(self):
        """Filtra los bins por el negocio del usuario actual"""
        user = self.request.user
        business = None
        
        # Verificar si el usuario tiene un negocio directamente asociado
        if hasattr(user, 'business') and user.business:
            business = user.business
        else:
            # Buscar el negocio en el perfil del usuario
            try:
                perfil = Perfil.objects.get(user=user)
                if perfil.business:
                    business = perfil.business
            except Perfil.DoesNotExist:
                pass
        
        if business:
            return FruitBin.objects.filter(business=business)
        return FruitBin.objects.none()
    
    def get_serializer_class(self):
        """Usa el serializador detallado para retrieve y el de lista para el resto"""
        if self.action == 'retrieve':
            return FruitBinDetailSerializer
        return FruitBinListSerializer



class FruitBinBulkCreateView(APIView):
    """Vista para crear múltiples bins de fruta con los mismos datos"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Endpoint para crear múltiples bins de fruta con los mismos datos"""
        serializer = FruitBinBulkCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            business = None
            
            # Verificar si el usuario tiene un negocio directamente asociado
            if hasattr(user, 'business') and user.business:
                business = user.business
            else:
                # Buscar el negocio en el perfil del usuario
                try:
                    perfil = Perfil.objects.get(user=user)
                    if perfil.business:
                        business = perfil.business
                except Perfil.DoesNotExist:
                    pass
            
            if not business:
                return Response(
                    {'detail': 'Usuario no tiene un negocio asociado'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Crear los bins
            bins = serializer.save(business=business)
            
            # Devolver la respuesta con los bins creados
            response_data = {
                'cantidad_creada': len(bins),
                'mensaje': f'Se han creado {len(bins)} bins correctamente',
                'bins': FruitBinListSerializer(bins, many=True).data
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
