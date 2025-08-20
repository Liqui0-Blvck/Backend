from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness

from .models import ConcessionSettlement, ConcessionSettlementDetail, FruitLot
from .serializers import ConcessionSettlementSerializer, ConcessionSettlementDetailSerializer
from .views import RolePermissionMixin


class ConcessionSettlementViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = ConcessionSettlementSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = ConcessionSettlement.objects.all()
    lookup_field = 'uid'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtrar por proveedor si se proporciona el parámetro
        proveedor_uid = self.request.query_params.get('proveedor', None)
        if proveedor_uid:
            qs = qs.filter(proveedor__uid=proveedor_uid)
        
        # Filtrar por estado si se proporciona el parámetro
        estado = self.request.query_params.get('estado', None)
        if estado:
            qs = qs.filter(estado=estado)
            
        return qs
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
    
    @action(detail=True, methods=['post'])
    def marcar_como_pagado(self, request, uid=None):
        """Marca una liquidación de concesión como pagada"""
        liquidacion = self.get_object()
        
        # Verificar si ya está pagada
        if liquidacion.estado == 'pagado':
            return Response({'detail': 'Esta liquidación ya está marcada como pagada'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar estado y guardar comprobante si se proporciona
        liquidacion.estado = 'pagado'
        
        # Si se proporciona un comprobante, guardarlo
        comprobante = request.data.get('comprobante', None)
        if comprobante:
            liquidacion.comprobante = comprobante
            
        # Guardar notas si se proporcionan
        notas = request.data.get('notas', None)
        if notas:
            liquidacion.notas = notas
            
        liquidacion.save()
        
        return Response({'detail': 'Liquidación marcada como pagada exitosamente'}, 
                        status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, uid=None):
        """Cancela una liquidación de concesión"""
        liquidacion = self.get_object()
        
        # Verificar si ya está pagada (no se puede cancelar una liquidación pagada)
        if liquidacion.estado == 'pagado':
            return Response({'detail': 'No se puede cancelar una liquidación que ya está pagada'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar estado
        liquidacion.estado = 'cancelado'
        
        # Guardar notas si se proporcionan
        notas = request.data.get('notas', None)
        if notas:
            liquidacion.notas = notas
            
        liquidacion.save()
        
        return Response({'detail': 'Liquidación cancelada exitosamente'}, 
                        status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def lotes_pendientes_liquidacion(self, request):
        """Obtiene los lotes en concesión que tienen ventas pendientes de liquidar"""
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado para el usuario'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener el proveedor si se proporciona
        proveedor_uid = request.query_params.get('proveedor', None)
        
        # Filtrar lotes en concesión
        lotes = FruitLot.objects.filter(
            business=perfil.business,
            en_concesion=True
        )
        
        # Filtrar por proveedor si se proporciona
        if proveedor_uid:
            lotes = lotes.filter(propietario_original__uid=proveedor_uid)
        
        # Filtrar lotes que tienen ventas no liquidadas
        # Esto requiere una lógica más compleja que se implementaría aquí
        # Por ahora, simplemente devolvemos todos los lotes en concesión
        
        from .serializers import FruitLotSerializer
        serializer = FruitLotSerializer(lotes, many=True)
        return Response(serializer.data)


class ConcessionSettlementDetailViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = ConcessionSettlementDetailSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = ConcessionSettlementDetail.objects.all()
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtrar por liquidación si se proporciona el parámetro
        liquidacion_uid = self.request.query_params.get('liquidacion', None)
        if liquidacion_uid:
            qs = qs.filter(liquidacion__uid=liquidacion_uid)
            
        return qs
