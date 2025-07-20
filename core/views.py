from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta
from sales.models import Sale, Customer, SalePending
from inventory.models import Product, FruitLot, StockReservation
from shifts.models import Shift
from business.models import Business
from accounts.models import CustomUser
from django.db.models import Sum, Count, F, Q, Value as V, CharField, DecimalField, IntegerField, DateTimeField
from django.db import models
from accounts.authentication import CustomJWTAuthentication
from accounts.models import Perfil
from itertools import chain
from django.db.models.functions import Coalesce

class DashboardView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_timeline(self, business, start_date, end_date, limit=50):
        """Genera un timeline con los eventos más relevantes del negocio."""
        # Ventas realizadas
        ventas = Sale.objects.filter(
            business=business, 
            created_at__range=[start_date, end_date]
        ).annotate(
            event_type=models.Value('Sale'),
            event_date=F('created_at'),
            description=models.Value('Venta'),
            subtitle=models.Value(''),
            amount=F('total'),
            quantity=F('peso_vendido'),
            event_id=F('id'),
        ).values(
            'event_type', 'event_date', 'description', 'subtitle', 
            'amount', 'quantity', 'event_id', 'metodo_pago'
        )
        
        # Reservas de stock
        reservas = StockReservation.objects.filter(
            lote__business=business, 
            created_at__range=[start_date, end_date]
        ).annotate(
            event_type=models.Value('Reserva'),
            event_date=F('created_at'),
            description=models.Value('Reserva de stock'),
            subtitle=models.Value(''),
            amount=models.Value(0),
            quantity=F('cantidad_kg'),
            event_id=F('id'),
        ).values(
            'event_type', 'event_date', 'description', 'subtitle', 
            'amount', 'quantity', 'event_id', 'estado'
        )
        
        # Lotes nuevos
        lotes = FruitLot.objects.filter(
            business=business, 
            created_at__range=[start_date, end_date]
        ).annotate(
            event_type=models.Value('Lote'),
            event_date=F('created_at'),
            description=models.Value('Nuevo lote'),
            subtitle=F('proveedor'),
            amount=models.Value(0),
            quantity=F('peso_neto'),
            event_id=F('id'),
        ).values(
            'event_type', 'event_date', 'description', 'subtitle', 
            'amount', 'quantity', 'event_id'
        )
        
        # Ventas pendientes
        pendientes = SalePending.objects.filter(
            business=business, 
            created_at__range=[start_date, end_date]
        ).annotate(
            event_type=models.Value('Pendiente'),
            event_date=F('created_at'),
            description=models.Value('Venta pendiente'),
            subtitle=models.Value(''),
            amount=models.Value(0),
            quantity=F('cantidad_kg'),
            event_id=F('id'),
        ).values(
            'event_type', 'event_date', 'description', 'subtitle', 
            'amount', 'quantity', 'event_id', 'estado'
        )
        
        # Combinamos todos los eventos
        all_events = list(chain(ventas, reservas, lotes, pendientes))
        
        # Ordenamos por fecha (más reciente primero) y limitamos
        sorted_events = sorted(all_events, key=lambda x: x['event_date'], reverse=True)[:limit]
        
        return sorted_events

    def get(self, request):
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        business = perfil.business
        # Filtros
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        group_by = request.query_params.get('group_by')  # day, week, month

        # Default: últimos 30 días
        if not end_date:
            end_date = datetime.now().date()
        else:
            end_date = parse_date(end_date)
        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = parse_date(start_date)

        # Ventas
        sales_qs = Sale.objects.filter(business=business, created_at__range=[start_date, end_date])
        total_ventas = sales_qs.count()
        total_kilos = sales_qs.aggregate(total=Sum('peso_vendido'))['total'] or 0
        total_ingresos = sales_qs.aggregate(total=Sum('total'))['total'] or 0

        # Ventas agrupadas
        sales_by_date = sales_qs.extra({'date': "date(created_at)"}).values('date').annotate(
            total_ventas=Count('id'),
            total_kilos=Sum('peso_vendido'),
            total_ingresos=Sum('total')
        ).order_by('date')

        # Productos
        productos = Product.objects.filter(business=business)
        productos_count = productos.count()

        # Stock actual por producto
        stock = FruitLot.objects.filter(business=business).values('producto__nombre').annotate(
            cajas=Sum('cantidad_cajas'),
            kilos=Sum('peso_neto')
        )

        # Reservas de stock
        reservas = StockReservation.objects.filter(lote__business=business, created_at__range=[start_date, end_date])
        reservas_count = reservas.count()
        reservas_pendientes = reservas.filter(estado='pendiente').count()

        # Clientes
        clientes = Customer.objects.filter(business=business)
        clientes_count = clientes.count()
        nuevos_clientes = clientes.filter(created_at__range=[start_date, end_date]).count()

        # Turnos
        turnos = Shift.objects.filter(business=business, fecha_apertura__range=[start_date, end_date])
        turnos_count = turnos.count()
        turnos_abiertos = turnos.filter(fecha_cierre__isnull=True).count()

        # Usuarios
        usuarios = (
            Perfil.objects
            .filter(business=business, user__groups__isnull=False)
            .values(rol=F('user__groups__name'))
            .annotate(total=Count('id'))
            .order_by('rol')
        )
        
        # Timeline de actividades
        timeline = self.get_timeline(business, start_date, end_date)

        return Response({
            'totales': {
                'ventas': total_ventas,
                'kilos_vendidos': total_kilos,
                'total_ingresos': total_ingresos,
                'productos': productos_count,
                'clientes': clientes_count,
                'nuevos_clientes': nuevos_clientes,
                'reservas': reservas_count,
                'reservas_pendientes': reservas_pendientes,
                'turnos': turnos_count,
                'turnos_abiertos': turnos_abiertos,
            },
            'ventas_por_fecha': list(sales_by_date),
            'stock': list(stock),
            'usuarios_por_rol': list(usuarios),
            'timeline': timeline,
        })

