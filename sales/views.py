from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Sale, SalePending, Customer
from .serializers import SaleSerializer, SalePendingSerializer, CustomerSerializer
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from django.db import transaction
from rest_framework.exceptions import ValidationError
from inventory.models import FruitLot
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta

class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
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


class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'uid'
    
    @action(detail=False, methods=['get'])
    def customers(self, request):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
            
        # Filtrado base por negocio - siempre traemos todos los clientes del negocio
        queryset = Customer.objects.filter(business=perfil.business)
        
        
        serializer = CustomerSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Sale.objects.none()
            
        # Filtrado base por negocio
        queryset = Sale.objects.filter(business=perfil.business)
        
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
        from decimal import Decimal
        # Concurrencia: bloquea el lote para evitar ventas simultáneas
        lote_uid = self.request.data.get('lote')
        peso_vendido = Decimal(str(self.request.data.get('peso_vendido', 0)))
        cajas_vendidas = int(self.request.data.get('cajas_vendidas', 0))
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        # Buscar el lote por uid en lugar de id
        lote = FruitLot.objects.select_for_update().get(uid=lote_uid, business=perfil.business)
        if lote.cantidad_cajas < cajas_vendidas:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'No hay suficientes cajas disponibles en el lote'})
        # Descuenta cajas y kilos (para trazabilidad, pero el control real es por cajas)
        lote.cantidad_cajas -= cajas_vendidas
        if lote.peso_neto is not None:
            lote.peso_neto = max(Decimal('0'), lote.peso_neto - peso_vendido)
        lote.save()
        perfil = getattr(self.request.user, 'perfil', None)
        serializer.save(vendedor=self.request.user, business=perfil.business)
