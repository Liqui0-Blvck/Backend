from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from .models import FruitLot
from datetime import datetime, timedelta

class MaduracionPaltasView(APIView):
    """
    Vista para manejar la información de maduración de paltas.
    Proporciona datos específicos sobre el estado de maduración de los lotes de paltas.
    """
    permission_classes = [IsAuthenticated, IsSameBusiness]
    
    def get(self, request, format=None):
        business = request.user.perfil.business
        
        # Filtrar lotes de paltas (productos que contienen 'palta' o 'aguacate' en su nombre)
        lotes_paltas = FruitLot.objects.filter(
            business=business,
            producto__nombre__icontains='palta'
        ).select_related('producto', 'box_type').order_by('fecha_ingreso')
        
        # También incluir productos con 'aguacate' en su nombre (término usado en algunos países)
        lotes_aguacate = FruitLot.objects.filter(
            business=business,
            producto__nombre__icontains='aguacate'
        ).select_related('producto', 'box_type').order_by('fecha_ingreso')
        
        # Combinar los queryset
        lotes_paltas = lotes_paltas.union(lotes_aguacate)
        
        # Preparar datos de respuesta
        data = []
        for lote in lotes_paltas:
            # Calcular días desde ingreso
            dias_desde_ingreso = (datetime.now().date() - lote.fecha_ingreso).days
            
            # Determinar color según estado de maduración
            color = {
                'verde': '#4CAF50',  # Verde
                'pre-maduro': '#FFC107',  # Amarillo
                'maduro': '#FF9800',  # Naranja
                'sobremaduro': '#F44336',  # Rojo
            }.get(lote.estado_maduracion, '#9E9E9E')  # Gris por defecto
            
            # Calcular porcentaje de maduración
            porcentaje_maduracion = {
                'verde': 0,
                'pre-maduro': 33,
                'maduro': 66,
                'sobremaduro': 100
            }.get(lote.estado_maduracion, 0)
            
            # Agregar datos del lote
            lote_data = {
                'id': lote.id,
                'producto_nombre': lote.producto.nombre,
                'calibre': lote.calibre,
                'fecha_ingreso': lote.fecha_ingreso,
                'dias_desde_ingreso': dias_desde_ingreso,
                'estado_maduracion': lote.estado_maduracion,
                'porcentaje_maduracion': porcentaje_maduracion,
                'color': color,
                'porcentaje_perdida_estimado': lote.porcentaje_perdida_estimado,
                'peso_neto': lote.peso_neto,
                'cantidad_cajas': lote.cantidad_cajas,
                'box_type_nombre': lote.box_type.nombre if lote.box_type else None,
            }
            
            data.append(lote_data)
        
        return Response(data)
