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


class SalePendingViewSet(viewsets.ModelViewSet):
    queryset = SalePending.objects.all()
    serializer_class = SalePendingSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    lookup_field = 'uid'

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
        cliente_uid = data.get('cliente')  # Ahora esperamos el UID del cliente
        cantidad_kg = float(data.get('peso_vendido', data.get('cantidad_kg', 0)))
        cantidad_cajas = int(data.get('cajas_vendidas', data.get('cantidad_cajas', 0)))
        precio_kg = float(data.get('precio_kg', 0))
        total = float(data.get('total', 0))
        metodo_pago = data.get('metodo_pago', '')
        vendedor_id = data.get('vendedor', None)
        business_id = data.get('business', None)
        vendedor = self.request.user
        comentarios = data.get('comentarios', '')
        # nombre_cliente = data.get('nombre_cliente')
        # rut_cliente = data.get('rut_cliente')
        # telefono_cliente = data.get('telefono_cliente')
        # email_cliente = data.get('email_cliente')
        
        # Obtener el perfil del usuario autenticado
        perfil = getattr(vendedor, 'perfil', None)
        if perfil is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Usuario sin perfil asociado'})
        
        # Usar el business del perfil si no se proporciona
        if not business_id:
            business = perfil.business
        else:
            from business.models import Business
            try:
                business = Business.objects.get(id=business_id)
            except Business.DoesNotExist:
                business = perfil.business

        # Buscar el cliente por UID si se proporciona
        nombre_cliente = None
        rut_cliente = None
        telefono_cliente = None
        email_cliente = None


        cliente = None
        if cliente_uid:
            try:
                from .models import Customer
                cliente = Customer.objects.get(uid=cliente_uid)
                nombre_cliente = cliente.nombre
                rut_cliente = cliente.rut
                telefono_cliente = cliente.telefono
                email_cliente = cliente.email
            except Customer.DoesNotExist:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'detail': f'Cliente con UID {cliente_uid} no encontrado'})

        from inventory.models import FruitLot, StockReservation
        # Buscar el lote por uid
        try:
            lote = FruitLot.objects.select_for_update().get(uid=lote_uid)
        except FruitLot.DoesNotExist:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': f'Lote con UID {lote_uid} no encontrado'})
            
        # Verificar stock disponible
        peso_disponible = lote.peso_disponible()
        if peso_disponible < cantidad_kg:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': f'Stock insuficiente en el lote. Disponible: {peso_disponible}kg, Solicitado: {cantidad_kg}kg'})
        
        # Crea SalePending
        sale_pending = serializer.save(
            lote=lote,
            cliente=cliente,
            cantidad_kg=cantidad_kg,
            cantidad_cajas=cantidad_cajas,
            nombre_cliente=nombre_cliente,
            rut_cliente=rut_cliente,
            telefono_cliente=telefono_cliente,
            email_cliente=email_cliente,
            vendedor=vendedor,
            comentarios=comentarios,
            business=business,
            estado="pendiente"
        )
        
        # Crea StockReservation coherente
        StockReservation.objects.create(
            lote=lote,
            usuario=vendedor,
            cantidad_kg=cantidad_kg,
            cantidad_cajas=cantidad_cajas,
            cliente=cliente,
            nombre_cliente=None if cliente else nombre_cliente,
            rut_cliente=None if cliente else rut_cliente,
            telefono_cliente=None if cliente else telefono_cliente,
            email_cliente=None if cliente else email_cliente,
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
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, uid=None):
        """Cancelar una venta de manera segura (soft delete)"""
        try:
            venta = self.get_object()
            
            # Verificar si la venta puede ser cancelada
            puede_cancelar, mensaje = venta.puede_cancelarse()
            if not puede_cancelar:
                return Response(
                    {"detail": mensaje}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtener datos de la solicitud
            motivo = request.data.get('motivo', '')
            usuario_autoriza_id = request.data.get('usuario_autoriza')
            
            # Obtener usuario que autoriza (opcional)
            usuario_autoriza = None
            if usuario_autoriza_id:
                try:
                    from accounts.models import CustomUser
                    usuario_autoriza = CustomUser.objects.get(id=usuario_autoriza_id)
                except CustomUser.DoesNotExist:
                    return Response(
                        {"detail": "Usuario autorizador no encontrado"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Cancelar la venta
            venta.cancelar_venta(
                usuario_cancela=request.user,
                usuario_autoriza=usuario_autoriza,
                motivo=motivo
            )
            
            # Serializar la venta actualizada
            serializer = self.get_serializer(venta)
            
            return Response({
                "detail": "Venta cancelada exitosamente",
                "venta": serializer.data
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {"detail": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"Error al cancelar la venta: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
        
        # Filtrado por estado de pago (booleano pagado)
        pagado = self.request.query_params.get('pagado', None)
        if pagado is not None:
            pagado_bool = pagado.lower() == 'true'
            queryset = queryset.filter(pagado=pagado_bool)
            
        # Filtrado por estado_pago específico (pendiente, parcial, completo, cerrada)
        estado_pago = self.request.query_params.get('estado_pago', None)
        if estado_pago:
            queryset = queryset.filter(estado_pago=estado_pago)
        
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
        notas = request.data.get('observaciones', request.data.get('notas', ''))
        
        # Obtener ventas_uids - aceptar tanto ventas_uids como compra_numero_orden
        ventas_uids = request.data.get('ventas_uids', [])
        compra_numero_orden = request.data.get('compra_numero_orden')
        
        # Si se proporciona compra_numero_orden, usarlo como venta a asociar
        if compra_numero_orden and not ventas_uids:
            ventas_uids = [compra_numero_orden]
        
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
        
        with transaction.atomic():
            # Crear el pago
            pago = CustomerPayment(
                cliente=cliente,
                business=perfil.business,
                monto=monto,
                metodo_pago=metodo_pago,
                referencia=referencia,
                notas=notas
            )
            pago.save()
            
            # Determinar cómo aplicar el pago
            ventas_a_pagar = None
            
            # Caso 1: Se especificaron ventas específicas para pagar
            if ventas_uids:
                # Convertir ventas_uids a strings si son objetos UUID
                ventas_uids_str = [str(uid) for uid in ventas_uids]
                
                # Buscar ventas por uid
                ventas_a_pagar = Sale.objects.filter(uid__in=ventas_uids_str, cliente=cliente)
                
                # Si no se encuentran ventas, intentar buscar por código de venta
                if not ventas_a_pagar.exists():
                    ventas_a_pagar = Sale.objects.filter(codigo_venta__in=ventas_uids_str, cliente=cliente)
                
                # Si aún no se encuentran, intentar búsqueda más flexible
                if not ventas_a_pagar.exists():
                    print(f"No se encontraron ventas con los UIDs proporcionados: {ventas_uids_str}")
                    for uid in ventas_uids_str:
                        try:
                            # Búsqueda más flexible
                            venta = Sale.objects.filter(
                                models.Q(uid__icontains=uid) | 
                                models.Q(codigo_venta__icontains=uid),
                                cliente=cliente
                            ).first()
                            if venta:
                                if ventas_a_pagar is None:
                                    ventas_a_pagar = [venta]
                                else:
                                    ventas_a_pagar = list(ventas_a_pagar) + [venta]
                        except Exception as e:
                            print(f"Error al buscar venta: {e}")
            
            # Caso 2: No se especificaron ventas, obtener automáticamente las ventas pendientes
            if not ventas_a_pagar or not ventas_a_pagar.exists():
                print("Obteniendo automáticamente ventas pendientes del cliente...")
                # Obtener todas las ventas a crédito con saldo pendiente, ordenadas por fecha (más antiguas primero)
                ventas_a_pagar = Sale.objects.filter(
                    cliente=cliente,
                    metodo_pago='credito',
                    pagado=False,  # Solo las no pagadas completamente
                    saldo_pendiente__gt=0  # Con saldo pendiente mayor a cero
                ).order_by('created_at')
                
                if not ventas_a_pagar.exists():
                    print("No se encontraron ventas pendientes para este cliente.")
            
            # Aplicar el pago a las ventas encontradas
            if ventas_a_pagar and (isinstance(ventas_a_pagar, list) or ventas_a_pagar.exists()):
                # Usar el método asociar_ventas para manejar la asociación y marcado
                pago.asociar_ventas(ventas_a_pagar)
                print(f"Pago aplicado a ventas: {[getattr(v, 'uid', v.id) for v in ventas_a_pagar]}")
            else:
                print("No se encontraron ventas para aplicar el pago. Actualizando saldo general del cliente.")
                # Si no hay ventas específicas, simplemente aplicamos el pago al saldo general del cliente
                cliente.actualizar_saldo()
            
            # Devolver el pago creado con información actualizada del cliente
            serializer = CustomerPaymentSerializer(pago)
            cliente_serializer = CustomerSerializer(cliente)
            
            response_data = {
                'pago': serializer.data,
                'cliente': cliente_serializer.data
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
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
        
        # Obtener ventas a crédito del cliente que estén pendientes de pago
        ventas_credito = Sale.objects.filter(
            cliente=cliente, 
            metodo_pago='credito',
            pagado=False  # Solo ventas no pagadas
        ).order_by('-created_at')
        
        # Filtrar solo las ventas con saldo pendiente
        ordenes_pendientes = []
        for venta in ventas_credito:
            # Usar el campo saldo_pendiente de la venta, que ya está calculado correctamente
            # Este campo se actualiza cada vez que se registra un pago asociado a la venta
            saldo_venta = venta.saldo_pendiente
            if saldo_venta > 0:
                # Usar el uid como número de orden para mantener consistencia
                # Convertir UUID a string para evitar error de subscriptable
                uid_str = str(venta.uid) if venta.uid else ""
                ordenes_pendientes.append({
                    'numero_orden': uid_str,
                    'fecha': venta.created_at,
                    'total': venta.total,
                    'monto_pendiente': saldo_venta,
                    'descripcion': f"Venta {venta.codigo_venta} del {venta.created_at.strftime('%d/%m/%Y')}"
                })
        
        return Response(ordenes_pendientes)
        
    except Customer.DoesNotExist:
        return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)

