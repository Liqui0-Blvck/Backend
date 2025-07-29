from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Sale, SalePending, Customer, CustomerPayment
from .serializers import SaleSerializer, SalePendingSerializer, CustomerSerializer, CustomerPaymentSerializer
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.permissions import IsSameBusiness
from django.db import transaction
from rest_framework.exceptions import ValidationError
from inventory.models import FruitLot
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta
from decimal import Decimal

class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'uid'
    queryset = Customer.objects.all()

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Customer.objects.none()
        # Filtrado base por negocio - siempre traemos todos los clientes del negocio
        queryset = Customer.objects.filter(business=perfil.business)
        return queryset

    def perform_create(self, serializer):
        # Asignar automáticamente el negocio del usuario autenticado
        perfil = getattr(self.request.user, 'perfil', None)
        serializer.save(business=perfil.business)
    
    @action(detail=True, methods=['get'])
    def ventas(self, request, uid=None):
        """Obtener todas las ventas de un cliente específico"""
        cliente = self.get_object()
        ventas = Sale.objects.filter(cliente=cliente)
        serializer = SaleSerializer(ventas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def pagos(self, request, uid=None):
        """Obtener todos los pagos de un cliente específico"""
        cliente = self.get_object()
        pagos = CustomerPayment.objects.filter(cliente=cliente)
        serializer = CustomerPaymentSerializer(pagos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='actualizar-credito', url_name='actualizar-credito')
    def actualizar_credito(self, request, uid=None):
        """Actualizar la configuración de crédito de un cliente"""
        cliente = self.get_object()
        
        # Verificar permisos - solo administradores pueden modificar el crédito
        if not request.user.is_staff and not request.user.is_superuser:
            return Response({"detail": "No tiene permisos para modificar el crédito"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # Actualizar campos de crédito
        credito_activo = request.data.get('credito_activo')
        limite_credito = request.data.get('limite_credito')
        
        if credito_activo is not None:
            cliente.credito_activo = credito_activo
        
        if limite_credito is not None:
            try:
                cliente.limite_credito = Decimal(str(limite_credito))
            except (ValueError, TypeError):
                return Response({"detail": "El límite de crédito debe ser un número válido"}, 
                                status=status.HTTP_400_BAD_REQUEST)
        
        cliente.save()
        serializer = self.get_serializer(cliente)
        return Response(serializer.data)



class SalePendingViewSet(viewsets.ModelViewSet):
    queryset = SalePending.objects.all()
    serializer_class = SalePendingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return SalePending.objects.none()
            
        # Filtrado base por negocio
        queryset = SalePending.objects.filter(business=perfil.business)
        
        # Filtrado por estado
        estado = self.request.query_params.get('estado', None)
        if estado:
            # Verificamos si es un estado válido
            estados_validos = [choice[0] for choice in SalePending.ESTADO_CHOICES]
            if estado in estados_validos:
                queryset = queryset.filter(estado=estado)
        
        # Filtrado por rango de fechas
        start_date_param = self.request.query_params.get('start_date', None)
        end_date_param = self.request.query_params.get('end_date', None)
        
        # Si no se proporcionan fechas, usamos los últimos 30 días por defecto
        if not start_date_param:
            start_date = datetime.now() - timedelta(days=30)
        else:
            start_date = parse_date(start_date_param)
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
        
        if not end_date_param:
            end_date = datetime.now()
        else:
            end_date = parse_date(end_date_param)
            if not end_date:
                end_date = datetime.now()
        
        # Aseguramos que end_date incluya todo el día
        if end_date:
            end_date = datetime.combine(end_date, datetime.max.time())
            
        return queryset.filter(created_at__range=[start_date, end_date])

    @transaction.atomic
    def perform_create(self, serializer):
        # Crear SalePending y StockReservation a la vez (campos coherentes)
        data = self.request.data
        lote_uid = data.get('lote')
        cliente_id = data.get('cliente')
        cantidad_kg = float(data.get('cantidad_kg', 0))
        cantidad_cajas = int(data.get('cantidad_cajas', 0))
        vendedor = self.request.user
        comentarios = data.get('comentarios', '')
        nombre_cliente = data.get('nombre_cliente')
        rut_cliente = data.get('rut_cliente')
        telefono_cliente = data.get('telefono_cliente')
        email_cliente = data.get('email_cliente')

        from inventory.models import FruitLot, StockReservation
        # Buscar el lote por uid en lugar de id
        lote = FruitLot.objects.select_for_update().get(uid=lote_uid, business=vendedor.business)
        if lote.peso_neto is not None and lote.peso_neto < cantidad_kg:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Stock insuficiente en el lote'})
        # Crea SalePending
        sale_pending = serializer.save(vendedor=vendedor, business=vendedor.business)
        # Crea StockReservation coherente (todos los campos)
        StockReservation.objects.create(
            lote=lote,
            usuario=vendedor,
            cantidad_kg=cantidad_kg,
            cantidad_cajas=cantidad_cajas,
            cliente_id=cliente_id or None,
            nombre_cliente=None if cliente_id else nombre_cliente,
            rut_cliente=None if cliente_id else rut_cliente,
            telefono_cliente=None if cliente_id else telefono_cliente,
            email_cliente=None if cliente_id else email_cliente,
            estado="en_proceso",
        )


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'uid'
    
    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Customer.objects.none()
        return Customer.objects.filter(business=perfil.business)


class CustomerPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerPaymentSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'uid'
    queryset = CustomerPayment.objects.all()

    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return CustomerPayment.objects.none()
        # Filtrado base por negocio
        queryset = CustomerPayment.objects.filter(business=perfil.business)
        
        # Filtrado por cliente
        cliente_uid = self.request.query_params.get('cliente', None)
        if cliente_uid:
            queryset = queryset.filter(cliente__uid=cliente_uid)
        
        return queryset

    def perform_create(self, serializer):
        # Asignar automáticamente el negocio del usuario autenticado
        perfil = getattr(self.request.user, 'perfil', None)
        serializer.save(business=perfil.business)
        
        # Actualizar el estado de las ventas asociadas si se marca como pagado
        pago = serializer.instance
        ventas_ids = self.request.data.get('ventas', [])
        
        if ventas_ids:
            # Asociar ventas al pago
            ventas = Sale.objects.filter(uid__in=ventas_ids, cliente=pago.cliente)
            pago.ventas.set(ventas)
            
            # Verificar si el pago cubre el total de las ventas
            total_ventas = sum(venta.total for venta in ventas)
            
            # Si el pago cubre el total, marcar las ventas como pagadas
            if pago.monto >= total_ventas:
                for venta in ventas:
                    venta.pagado = True
                    venta.save()


class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'uid'
    
    @action(detail=False, methods=['get'])
    def customers(self, request):
        """Obtener todos los clientes para seleccionar en una venta"""
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            return Response([])  # No hay perfil, no hay clientes
        
        clientes = Customer.objects.filter(business=perfil.business)
        serializer = CustomerSerializer(clientes, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Sale.objects.none()
        
        # Filtrado base por negocio
        queryset = Sale.objects.filter(business=perfil.business)
        
        # Filtrado por lote
        lote_uid = self.request.query_params.get('lote', None)
        if lote_uid:
            queryset = queryset.filter(lote__uid=lote_uid)
        
        # Filtrado por cliente
        cliente_uid = self.request.query_params.get('cliente', None)
        if cliente_uid:
            queryset = queryset.filter(cliente__uid=cliente_uid)
        
        # Filtrado por método de pago
        metodo_pago = self.request.query_params.get('metodo_pago', None)
        if metodo_pago:
            queryset = queryset.filter(metodo_pago=metodo_pago)
        
        # Filtrado por estado de pago
        pagado = self.request.query_params.get('pagado', None)
        if pagado is not None:
            pagado_bool = pagado.lower() == 'true'
            queryset = queryset.filter(pagado=pagado_bool)
        
        # Filtrado por rango de fechas
        start_date_param = self.request.query_params.get('start_date', None)
        end_date_param = self.request.query_params.get('end_date', None)
        
        # Si no se proporcionan fechas, usamos los últimos 30 días por defecto
        if not start_date_param:
            start_date = datetime.now() - timedelta(days=30)
        else:
            start_date = parse_date(start_date_param)
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
        
        if not end_date_param:
            end_date = datetime.now()
        else:
            end_date = parse_date(end_date_param)
            if not end_date:
                end_date = datetime.now()
        
        # Aseguramos que end_date incluya todo el día
        if end_date:
            end_date = datetime.combine(end_date, datetime.max.time())
            
        return queryset.filter(created_at__range=[start_date, end_date])
    
    def perform_create(self, serializer):
        # Asignar automáticamente el negocio del usuario autenticado
        perfil = getattr(self.request.user, 'perfil', None)
        serializer.save(business=perfil.business)


# Vista independiente para actualizar crédito de cliente
from rest_framework.decorators import api_view, permission_classes
from core.permissions import IsAdminOrOwner

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrOwner])
def actualizar_credito_cliente(request, uid):
    """Actualizar la configuración de crédito de un cliente"""
    try:
        cliente = Customer.objects.get(uid=uid)
            
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # Actualizar campos de crédito
        credito_activo = request.data.get('credito_activo')
        limite_credito = request.data.get('limite_credito')
        
        if credito_activo is not None:
            cliente.credito_activo = credito_activo
        
        if limite_credito is not None:
            try:
                cliente.limite_credito = Decimal(str(limite_credito))
            except (ValueError, TypeError):
                return Response({"detail": "El límite de crédito debe ser un número válido"}, 
                                status=status.HTTP_400_BAD_REQUEST)
        
        cliente.save()
        serializer = CustomerSerializer(cliente)
        return Response(serializer.data)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)
