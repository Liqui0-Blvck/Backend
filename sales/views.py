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


# Vistas independientes para operaciones de clientes
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ventas_cliente(request, uid):
    """Obtener todas las ventas de un cliente específico"""
    try:
        cliente = Customer.objects.get(uid=uid)
        
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        ventas = Sale.objects.filter(cliente=cliente).order_by('-created_at')
        serializer = SaleSerializer(ventas, many=True)
        return Response(serializer.data)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pagos_cliente(request, uid):
    """Obtener todos los pagos de un cliente específico"""
    try:
        cliente = Customer.objects.get(uid=uid)
        
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        pagos = CustomerPayment.objects.filter(cliente=cliente).order_by('-created_at')
        serializer = CustomerPaymentSerializer(pagos, many=True)
        return Response(serializer.data)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historial_completo_cliente(request, uid):
    """Obtener el historial completo de compras y pagos de un cliente específico"""
    try:
        cliente = Customer.objects.get(uid=uid)
        
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # Obtener todas las ventas (compras) del cliente
        ventas = Sale.objects.filter(cliente=cliente).order_by('-created_at')
        ventas_serializer = SaleSerializer(ventas, many=True)
        
        # Obtener todos los pagos del cliente
        pagos = CustomerPayment.objects.filter(cliente=cliente).order_by('-created_at')
        pagos_serializer = CustomerPaymentSerializer(pagos, many=True)
        
        # Calcular estadísticas de crédito
        total_compras = ventas.filter(metodo_pago='credito').count()
        monto_total_compras_credito = ventas.filter(metodo_pago='credito').aggregate(
            total=models.Sum('total')
        )['total'] or 0
        monto_total_pagos = pagos.aggregate(
            total=models.Sum('monto')
        )['total'] or 0
        
        # Construir respuesta con toda la información
        response_data = {
            'cliente': {
                'uid': cliente.uid,
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'credito_activo': cliente.credito_activo,
                'limite_credito': cliente.limite_credito,
                'saldo_actual': cliente.saldo_actual,
                'credito_disponible': cliente.credito_disponible
            },
            'resumen': {
                'total_compras': ventas.count(),
                'total_compras_credito': total_compras,
                'monto_total_compras': sum(venta.total for venta in ventas),
                'monto_total_compras_credito': monto_total_compras_credito,
                'monto_total_pagos': monto_total_pagos,
                'saldo_pendiente': monto_total_compras_credito - monto_total_pagos
            },
            'compras': ventas_serializer.data,
            'pagos': pagos_serializer.data
        }
        
        return Response(response_data)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_pago_cliente(request, uid):
    """Registrar un nuevo pago para un cliente específico"""
    try:
        cliente = Customer.objects.get(uid=uid)
        
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # Validar datos del pago
        monto = request.data.get('monto')
        metodo_pago = request.data.get('metodo_pago')
        referencia = request.data.get('referencia', '')
        notas = request.data.get('notas', '')
        
        # Validaciones básicas
        if not monto:
            return Response({"detail": "El monto del pago es requerido"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            monto = Decimal(str(monto))
            if monto <= 0:
                raise ValueError("El monto debe ser positivo")
        except (ValueError, TypeError):
            return Response({"detail": "El monto debe ser un número positivo válido"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        if not metodo_pago:
            return Response({"detail": "El método de pago es requerido"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Crear el pago
        pago = CustomerPayment(
            cliente=cliente,
            business=perfil.business,
            monto=monto,
            metodo_pago=metodo_pago,
            referencia=referencia,
            notas=notas,
            registrado_por=request.user
        )
        pago.save()
        
        # Devolver el pago creado
        serializer = CustomerPaymentSerializer(pago)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def informacion_deuda_cliente(request, uid):
    """Obtener información detallada sobre la deuda de un cliente específico"""
    try:
        cliente = Customer.objects.get(uid=uid)
        
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # Obtener ventas a crédito del cliente
        ventas_credito = Sale.objects.filter(
            cliente=cliente, 
            metodo_pago='credito'
        ).order_by('-created_at')
        
        # Obtener pagos del cliente
        pagos = CustomerPayment.objects.filter(cliente=cliente).order_by('-created_at')
        
        # Calcular montos totales
        monto_total_credito = ventas_credito.aggregate(total=models.Sum('total'))['total'] or 0
        monto_total_pagos = pagos.aggregate(total=models.Sum('monto'))['total'] or 0
        saldo_pendiente = monto_total_credito - monto_total_pagos
        
        # Obtener ventas pendientes de pago (con saldo > 0)
        ventas_pendientes = []
        for venta in ventas_credito:
            # Calcular pagos aplicados a esta venta
            pagos_venta = CustomerPayment.objects.filter(
                cliente=cliente,
                venta=venta
            ).aggregate(total=models.Sum('monto'))['total'] or 0
            
            saldo_venta = venta.total - pagos_venta
            if saldo_venta > 0:
                ventas_pendientes.append({
                    'uid': venta.uid,
                    'fecha': venta.created_at,
                    'total': venta.total,
                    'pagado': pagos_venta,
                    'saldo_pendiente': saldo_venta
                })
        
        # Construir respuesta detallada
        response_data = {
            'cliente': {
                'uid': cliente.uid,
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'credito_activo': cliente.credito_activo,
                'limite_credito': cliente.limite_credito,
                'saldo_actual': cliente.saldo_actual,
                'credito_disponible': cliente.credito_disponible
            },
            'resumen_deuda': {
                'total_ventas_credito': monto_total_credito,
                'total_pagos_realizados': monto_total_pagos,
                'saldo_pendiente': saldo_pendiente,
                'porcentaje_utilizado': round((saldo_pendiente / cliente.limite_credito * 100) 
                                             if cliente.limite_credito > 0 else 0, 2)
            },
            'ventas_pendientes': ventas_pendientes,
            'ultimos_pagos': CustomerPaymentSerializer(pagos[:5], many=True).data
        }
        
        return Response(response_data)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ordenes_pendientes_cliente(request, uid):
    """Obtener lista de órdenes pendientes de pago para un cliente específico"""
    try:
        cliente = Customer.objects.get(uid=uid)
        
        # Verificar que el cliente pertenece al mismo negocio que el usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or cliente.business != perfil.business:
            return Response({"detail": "No tiene acceso a este cliente"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # Obtener ventas a crédito del cliente
        ventas_credito = Sale.objects.filter(
            cliente=cliente, 
            metodo_pago='credito'
        ).order_by('-created_at')
        
        # Filtrar solo las ventas con saldo pendiente
        ordenes_pendientes = []
        for venta in ventas_credito:
            # Calcular pagos aplicados a esta venta
            # Verificar si el modelo CustomerPayment tiene un campo para relacionar con la venta
            # Si no lo tiene, simplemente calculamos el total de pagos del cliente
            pagos_venta = 0
            try:
                # Intentamos filtrar por venta si existe el campo
                if hasattr(CustomerPayment, 'venta'):
                    pagos_venta = CustomerPayment.objects.filter(
                        cliente=cliente,
                        venta=venta
                    ).aggregate(total=models.Sum('monto'))['total'] or 0
                else:
                    # Si no existe el campo, no podemos filtrar por venta específica
                    # Asumimos que todos los pagos van al saldo general
                    pass
            except Exception as e:
                print(f"Error al calcular pagos por venta: {e}")
            
            # Para este ejemplo, asumimos que el saldo es el total de la venta
            # ya que no podemos determinar pagos específicos por venta
            saldo_venta = venta.total
            if saldo_venta > 0:
                # Usar el uid como número de orden para mantener consistencia
                # Convertir UUID a string para evitar error de subscriptable
                uid_str = str(venta.uid) if venta.uid else ""
                ordenes_pendientes.append({
                    'numero_orden': uid_str,
                    'fecha': venta.created_at,
                    'total': venta.total,
                    'monto_pendiente': saldo_venta,
                    'descripcion': f"Venta {uid_str[:8] if len(uid_str) >= 8 else uid_str} del {venta.created_at.strftime('%d/%m/%Y')}"
                })
        
        return Response(ordenes_pendientes)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)

