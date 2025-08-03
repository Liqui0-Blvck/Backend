from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Shift, ShiftExpense
from .serializers import ShiftSerializer, ShiftExpenseSerializer
from .serializers_detail import ShiftDetailSerializer
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness

class ShiftViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    
    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Shift.objects.none()
        return Shift.objects.filter(business=perfil.business)
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
    
    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)


class ShiftExpenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar los gastos incurridos durante un turno.
    Permite crear, listar, actualizar y eliminar gastos asociados a un turno específico.
    """
    serializer_class = ShiftExpenseSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    
    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return ShiftExpense.objects.none()
        
        # Filtrar por turno si se especifica
        shift_id = self.request.query_params.get('shift', None)
        queryset = ShiftExpense.objects.filter(business=perfil.business)
        
        if shift_id:
            queryset = queryset.filter(shift_id=shift_id)
            
        return queryset.order_by('-fecha')
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        
        # Verificar que el turno exista y pertenezca al mismo negocio
        shift_id = self.request.data.get('shift')
        if shift_id:
            try:
                shift = Shift.objects.get(pk=shift_id, business=perfil.business)
            except Shift.DoesNotExist:
                raise ValidationError({'detail': 'Turno no encontrado o no pertenece a este negocio'})
        
        # Por defecto, el usuario que registra el gasto es el usuario actual
        serializer.save(
            business=perfil.business,
            registrado_por=user
        )
    
    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
            
        # Verificar que el turno exista y pertenezca al mismo negocio
        shift_id = self.request.data.get('shift')
        if shift_id:
            try:
                shift = Shift.objects.get(pk=shift_id, business=perfil.business)
            except Shift.DoesNotExist:
                raise ValidationError({'detail': 'Turno no encontrado o no pertenece a este negocio'})
        
        serializer.save(business=perfil.business)
    
    @action(detail=False, methods=['get'])
    def por_turno(self, request):
        """
        Devuelve todos los gastos asociados a un turno específico.
        """
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        
        shift_id = request.query_params.get('shift_id', None)
        if not shift_id:
            return Response({'detail': 'Se requiere el ID del turno.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            shift = Shift.objects.get(pk=shift_id, business=perfil.business)
        except Shift.DoesNotExist:
            return Response({'detail': 'Turno no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        
        gastos = ShiftExpense.objects.filter(shift=shift).order_by('-fecha')
        serializer = self.get_serializer(gastos, many=True)
        
        # Calcular totales
        total_gastos = sum(float(gasto.monto) for gasto in gastos)
        
        # Agrupar por categoría
        categorias = {}
        for gasto in gastos:
            categoria = gasto.get_categoria_display()
            if categoria not in categorias:
                categorias[categoria] = 0
            categorias[categoria] += float(gasto.monto)
        
        return Response({
            'gastos': serializer.data,
            'total_gastos': total_gastos,
            'gastos_por_categoria': [{'categoria': k, 'monto': v} for k, v in categorias.items()],
            'cantidad_gastos': len(gastos)
        })
    
    @action(detail=False, methods=['get'])
    def estado(self, request):
        """
        Devuelve información sobre el turno activo en el negocio.
        En el nuevo modelo, solo puede haber un turno activo a la vez por negocio.
        """
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        # Obtener el único turno activo en el negocio
        turno_activo = Shift.objects.filter(
            business=perfil.business,
            estado="abierto"
        ).select_related('usuario_abre').first()
        
        if turno_activo:
            usuario_nombre = f"{turno_activo.usuario_abre.first_name} {turno_activo.usuario_abre.last_name}".strip() or turno_activo.usuario_abre.username
            es_del_usuario_actual = turno_activo.usuario_abre.id == user.id
            
            turno_data = {
                'id': turno_activo.id,
                'usuario_id': turno_activo.usuario_abre.id,
                'usuario_nombre': usuario_nombre,
                'fecha_apertura': turno_activo.fecha_apertura,
                'es_del_usuario_actual': es_del_usuario_actual,
                'detalle': ShiftSerializer(turno_activo).data
            }
        else:
            turno_data = None
        
        # Obtener el último turno cerrado para referencia
        ultimo_turno_cerrado = Shift.objects.filter(
            business=perfil.business,
            estado="cerrado"
        ).order_by('-fecha_cierre').first()
        
        return Response({
            'hay_turno_activo': turno_activo is not None,
            'turno_activo': turno_data,
            'ultimo_turno_cerrado': ShiftSerializer(ultimo_turno_cerrado).data if ultimo_turno_cerrado else None,
            'puede_iniciar_turno': turno_activo is None  # Solo se puede iniciar si no hay turno activo
        })
    
    @action(detail=False, methods=['post'])
    def iniciar(self, request):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        # Usar transacción para garantizar consistencia
        with transaction.atomic():
            # Verificar si hay algún turno abierto en el negocio
            turnos_abiertos = Shift.objects.filter(
                business=perfil.business,
                estado="abierto"
            ).select_for_update()
            
            # Cerrar automáticamente cualquier turno abierto
            turnos_cerrados = []
            for turno in turnos_abiertos:
                turno.estado = "cerrado"
                turno.usuario_cierra = user
                turno.fecha_cierre = timezone.now()
                turno.motivo_diferencia = "Cerrado automáticamente al iniciar nuevo turno"
                turno.save()
                turnos_cerrados.append(ShiftSerializer(turno).data)
            
            # Crear nuevo turno
            turno_nuevo = Shift.objects.create(
                business=perfil.business,
                usuario_abre=user,
                fecha_apertura=timezone.now(),
                estado="abierto"
            )
        
        # Preparar respuesta
        respuesta = {
            'turno_nuevo': ShiftSerializer(turno_nuevo).data,
            'turnos_cerrados': turnos_cerrados,
            'turnos_cerrados_cantidad': len(turnos_cerrados)
        }
        
        return Response(respuesta, status=201)
    
    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        try:
            turno = Shift.objects.get(pk=pk, business=perfil.business)
        except Shift.DoesNotExist:
            return Response({'detail': 'Turno no encontrado.'}, status=404)
        
        if turno.estado == "cerrado":
            return Response({'detail': 'Este turno ya está cerrado.'}, status=400)
        
        # Cerrar el turno
        turno.estado = "cerrado"
        turno.usuario_cierra = user
        turno.fecha_cierre = timezone.now()
        turno.motivo_diferencia = request.data.get('motivo_diferencia', '')
        turno.save()
        
        return Response(ShiftSerializer(turno).data)
        
    @action(detail=True, methods=['get'])
    def detalle(self, request, pk=None):
        """
        Devuelve información detallada sobre un turno específico, incluyendo:
        - Información básica del turno
        - Resumen de ventas
        - Movimientos de inventario
        - Transacciones financieras
        """
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        try:
            turno = Shift.objects.get(pk=pk, business=perfil.business)
        except Shift.DoesNotExist:
            return Response({'detail': 'Turno no encontrado.'}, status=404)
        
        serializer = ShiftDetailSerializer(turno)
        return Response(serializer.data)
