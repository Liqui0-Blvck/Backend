from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import FruitLot
from business.models import Business
from .serializers_detail import FruitLotDetailSerializer
from core.permissions import IsSameBusiness


class FruitLotDetailViewSet(viewsets.ViewSet):
    """
    ViewSet para obtener detalles completos de un lote de fruta.
    """
    permission_classes = [IsAuthenticated, IsSameBusiness]
    
    def get_detail(self, request, uid=None):
        """
        Obtiene los detalles completos de un lote de fruta por su UID.
        
        Devuelve una estructura JSON detallada con toda la información del lote,
        incluyendo métricas calculadas, recomendaciones y historiales.
        """
        user = request.user
        perfil = getattr(user, 'perfil', None)
        
        # Validar que el usuario tenga un perfil
        if perfil is None and not user.is_staff:
            return Response(
                {'detail': 'Perfil no encontrado para el usuario'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Obtener el negocio del usuario
        business = perfil.business if perfil else None
        
        # Para usuarios staff sin perfil, permitir acceso a todos los lotes
        if user.is_staff and not business:
            lote = get_object_or_404(FruitLot, uid=uid)
        else:
            # Para usuarios normales, filtrar por negocio
            lote = get_object_or_404(FruitLot, uid=uid, business=business)
        
        # Serializar el lote con el serializador detallado
        serializer = FruitLotDetailSerializer(lote)
        
        # Devolver la respuesta en el formato exacto solicitado
        return Response({
            'success': True,
            'data': serializer.data
        })
