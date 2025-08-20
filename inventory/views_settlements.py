from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from core.permissions import IsSameBusiness
from .models import ConcessionSettlement
from .serializers import ConcessionSettlementSerializer
from .views import RolePermissionMixin

class ConcessionSettlementViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    """ViewSet para manejar liquidaciones de concesión"""
    serializer_class = ConcessionSettlementSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = ConcessionSettlement.objects.all()
    lookup_field = 'uid'
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        proveedor_uid = self.request.query_params.get('proveedor', None)
        
        if proveedor_uid:
            queryset = queryset.filter(proveedor__uid=proveedor_uid)
        
        return queryset
