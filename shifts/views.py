from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Shift, ShiftExpense, ShiftClosing, BoxRefill
from .serializers import ShiftSerializer, ShiftExpenseSerializer, ShiftClosingSerializer
from .serializers_detail import ShiftDetailSerializer, BoxRefillSerializer
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from .serializers import ShiftEstadoSerializer

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

    @action(detail=True, methods=['get'])
    def detalle(self, request, pk=None):
        """
        Devuelve información detallada sobre un turno específico, incluyendo ventas, gastos,
        movimientos de inventario, transacciones y el cuadro de caja.
        """
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        # Intentamos diferentes estrategias para encontrar el turno
        try:
            # 1) Buscar por UID de turno directamente
            try:
                turno = Shift.objects.get(uid=pk, business=perfil.business)
                serializer = ShiftDetailSerializer(turno)
                return Response(serializer.data)
            except Shift.DoesNotExist:
                pass

            # 2) Buscar un gasto por ID para derivar el turno
            try:
                gasto = ShiftExpense.objects.get(id=pk, business=perfil.business)
                turno = gasto.shift
                serializer = ShiftDetailSerializer(turno)
                return Response(serializer.data)
            except ShiftExpense.DoesNotExist:
                pass
            
            return Response({'detail': 'Turno o gasto no encontrado.'}, status=404)
            
        except Exception as e:
            return Response({'detail': f'Error al procesar la solicitud: {str(e)}'}, status=500)

    @action(detail=False, methods=['get'])
    def estado(self, request):
        """
        Devuelve información sobre el turno activo del negocio y el último cerrado.
        """
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        # Pasar el turno activo como instancia (o un objeto dummy) para evitar {}
        turno_activo = Shift.objects.filter(business=perfil.business, estado='abierto').first()
        serializer = ShiftEstadoSerializer(instance=turno_activo or object(), context={'business': perfil.business, 'user': user})
        data = serializer.to_representation(serializer.instance)
        return Response(data)

    @action(detail=False, methods=['post'])
    def iniciar(self, request):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        with transaction.atomic():
            turnos_abiertos = Shift.objects.filter(
                business=perfil.business,
                estado="abierto"
            ).select_for_update()
            
            turnos_cerrados = []
            for turno in turnos_abiertos:
                turno.estado = "cerrado"
                turno.usuario_cierra = user
                turno.fecha_cierre = timezone.now()
                turno.motivo_diferencia = "Cerrado automáticamente al iniciar nuevo turno"
                turno.save()
                turnos_cerrados.append(ShiftSerializer(turno).data)
            
            turno_nuevo = Shift.objects.create(
                business=perfil.business,
                usuario_abre=user,
                fecha_apertura=timezone.now(),
                estado="abierto"
            )
        
        respuesta = {
            'turno_nuevo': ShiftSerializer(turno_nuevo).data
        }
        
        return Response(respuesta, status=201)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        try:
            turno = Shift.objects.get(uid=pk, business=perfil.business)
        except Shift.DoesNotExist:
            return Response({'detail': 'Turno no encontrado.'}, status=404)
        
        if turno.estado == "cerrado":
            return Response({'detail': 'Este turno ya está cerrado.'}, status=400)
        
        turno.estado = "cerrado"
        turno.usuario_cierra = user
        turno.fecha_cierre = timezone.now()
        turno.motivo_diferencia = request.data.get('motivo_diferencia', '')
        turno.save()
        
        return Response(ShiftSerializer(turno).data)


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
            # Usar shift__uid en lugar de shift_id para filtrar correctamente por UUID
            queryset = queryset.filter(shift__uid=shift_id)
            
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
                shift = Shift.objects.get(uid=shift_id, business=perfil.business)
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
                shift = Shift.objects.get(uid=shift_id, business=perfil.business)
            except Shift.DoesNotExist:
                raise ValidationError({'detail': 'Turno no encontrado o no pertenece a este negocio'})
        else:
            # Si no viene en el payload, usar el shift ya asociado al cierre
            shift = getattr(serializer.instance, 'shift', None)

        # Asegurar turno cerrado también en update
        with transaction.atomic():
            if shift and shift.estado != 'cerrado':
                shift.estado = 'cerrado'
                shift.usuario_cierra = user
                shift.fecha_cierre = timezone.now()
                shift.save()
            fecha_cierre_caja = serializer.validated_data.get('fecha_cierre_caja') or getattr(serializer.instance, 'fecha_cierre_caja', None) or timezone.now()
            serializer.save(business=perfil.business, cerrado_por=user, shift=shift, fecha_cierre_caja=fecha_cierre_caja)


class BoxRefillViewSet(viewsets.ModelViewSet):
    """CRUD para `BoxRefill` (rellenos de cajas) registrado manualmente por el usuario."""
    serializer_class = BoxRefillSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return BoxRefill.objects.none()
        qs = BoxRefill.objects.filter(business=perfil.business)
        # Filtros opcionales
        shift_uid = self.request.query_params.get('shift')
        fruit_lot_id = self.request.query_params.get('fruit_lot')
        if shift_uid:
            qs = qs.filter(shift__uid=shift_uid)
        if fruit_lot_id:
            qs = qs.filter(fruit_lot_id=fruit_lot_id)
        return qs.order_by('-fecha')

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})

        # Validar y resolver shift por UID si viene como texto
        shift_uid = self.request.data.get('shift')
        if not shift_uid:
            raise ValidationError({'detail': 'Debe indicar el turno (shift UID).'})
        try:
            shift = Shift.objects.get(uid=shift_uid, business=perfil.business)
        except Shift.DoesNotExist:
            raise ValidationError({'detail': 'Turno no encontrado o no pertenece a este negocio'})
        # Enforce active shift as per business rule
        if shift.estado != 'abierto':
            raise ValidationError({'detail': 'Solo se puede registrar un relleno con un turno activo.'})

        # Validar que el lote pertenezca a la misma empresa
        fruit_lot_id = self.request.data.get('fruit_lot')
        if not fruit_lot_id:
            raise ValidationError({'detail': 'Debe indicar el lote (fruit_lot).'})
        # Evitar import circular al tope; validar por relación inversa de business si existe
        fruit_lot = shift  # placeholder para scope
        try:
            # Lazy import para evitar ciclos fuertes si los hubiera
            from inventory.models import FruitLot  # noqa
            fruit_lot = FruitLot.objects.get(id=fruit_lot_id)
        except Exception:
            raise ValidationError({'detail': 'Lote no encontrado.'})
        # Si FruitLot tiene business, validar (evitar operador walrus para compatibilidad)
        lot_business = getattr(fruit_lot, 'business', None)
        lot_business_id = getattr(lot_business, 'id', None) if lot_business else None
        if lot_business_id and lot_business_id != perfil.business.id:
            raise ValidationError({'detail': 'El lote no pertenece a este negocio'})

        cantidad_cajas = self.request.data.get('cantidad_cajas')
        try:
            if cantidad_cajas is None or int(cantidad_cajas) <= 0:
                raise ValidationError({'detail': 'La cantidad de cajas debe ser un entero positivo.'})
        except ValueError:
            raise ValidationError({'detail': 'La cantidad de cajas debe ser un entero positivo.'})

        serializer.save(business=perfil.business, usuario=user, shift=shift)

    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        # No permitimos cambiar de business; validamos scope
        instance = serializer.instance
        if instance.business_id != perfil.business.id:
            raise ValidationError({'detail': 'No autorizado para modificar este registro'})
        # Mantener usuario creador intacto; permitir editar cantidad y motivo
        serializer.save(business=perfil.business)

    def perform_destroy(self, instance):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        if instance.business_id != perfil.business.id:
            raise ValidationError({'detail': 'No autorizado para eliminar este registro'})
        return super().perform_destroy(instance)

class ShiftClosingViewSet(viewsets.ModelViewSet):
    """CRUD para cierres de caja por turno"""
    serializer_class = ShiftClosingSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return ShiftClosing.objects.none()
        qs = ShiftClosing.objects.filter(business=perfil.business)
        shift_uid = self.request.query_params.get('shift', None)
        if shift_uid:
            qs = qs.filter(shift__uid=shift_uid)
        return qs.order_by('-fecha_cierre_caja')

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        shift_uid = self.request.data.get('shift')
        try:
            shift = Shift.objects.get(uid=shift_uid, business=perfil.business)
        except Shift.DoesNotExist:
            raise ValidationError({'detail': 'Turno no encontrado o no pertenece a este negocio'})
        # Al crear el cierre, cerrar el turno asociado
        with transaction.atomic():
            if shift.estado != 'cerrado':
                shift.estado = 'cerrado'
                shift.usuario_cierra = user
                shift.fecha_cierre = timezone.now()
                shift.save()
            fecha_cierre_caja = serializer.validated_data.get('fecha_cierre_caja') or timezone.now()
            serializer.save(business=perfil.business, cerrado_por=user, shift=shift, fecha_cierre_caja=fecha_cierre_caja)

    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        # Resolver el shift por UID si viene en el payload; si no, usar el asociado
        shift_uid = self.request.data.get('shift')
        if shift_uid:
            try:
                shift = Shift.objects.get(uid=shift_uid, business=perfil.business)
            except Shift.DoesNotExist:
                raise ValidationError({'detail': 'Turno no encontrado o no pertenece a este negocio'})
        else:
            shift = getattr(serializer.instance, 'shift', None)

        # Cerrar el turno si aún no está cerrado y asegurar fecha de cierre de caja
        with transaction.atomic():
            if shift and shift.estado != 'cerrado':
                shift.estado = 'cerrado'
                shift.usuario_cierra = user
                shift.fecha_cierre = timezone.now()
                shift.save()
            fecha_cierre_caja = serializer.validated_data.get('fecha_cierre_caja') or getattr(serializer.instance, 'fecha_cierre_caja', None) or timezone.now()
            serializer.save(business=perfil.business, cerrado_por=user, shift=shift, fecha_cierre_caja=fecha_cierre_caja)
