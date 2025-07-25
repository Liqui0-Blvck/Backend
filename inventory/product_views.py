from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Product
from .serializers import ProductSerializer
from .product_movements import ProductMovementSerializer, ProductInfoSerializer, get_product_movements
from core.permissions import IsSameBusiness


class ProductMovementViewSet(viewsets.ModelViewSet):
    """
    ViewSet para obtener los movimientos de un producto específico
    """
    permission_classes = [IsAuthenticated, IsSameBusiness]
    serializer_class = ProductSerializer
    lookup_field = 'uid'
    
    def get_queryset(self):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        
        if perfil is None:
            return Product.objects.none()
        
        return Product.objects.filter(business=perfil.business)
    
    @action(detail=True, methods=['get'])
    def movements(self, request, uid=None):
        """
        Obtener el historial de movimientos de un producto específico
        """
        try:
            product = self.get_queryset().get(uid=uid)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Obtener información general del producto
            info_serializer = ProductInfoSerializer(product)
            
            # Obtener movimientos del producto
            movements = get_product_movements(uid)
            
            # Formatear los movimientos para que coincidan con el formato del frontend
            formatted_movements = []
            for m in movements:
                try:
                    # Convertir fecha a formato legible
                    fecha_str = m['fecha'].strftime("%d/%m/%y, %H:%M") if hasattr(m['fecha'], 'strftime') else str(m['fecha'])
                    
                    # Mapear tipo a los valores esperados por el frontend
                    tipo_formateado = 'Entrada'
                    if m['tipo'] == 'Salida':
                        tipo_formateado = 'Salida'
                    elif m['tipo'] == 'Ajuste':
                        tipo_formateado = 'Ajuste'
                    
                    # Formatear cantidad con signo
                    cantidad = m['cantidad']
                    if cantidad > 0 and m['tipo'] != 'Salida':
                        cantidad_str = f"+{cantidad}"
                    elif cantidad < 0 or m['tipo'] == 'Salida':
                        # Para salidas, mostrar la cantidad como negativa
                        if m['tipo'] == 'Salida' and cantidad > 0:
                            cantidad = -cantidad
                        cantidad_str = f"{cantidad}"
                    else:
                        cantidad_str = f"{cantidad}"
                    
                    formatted_movements.append({
                        'fecha': fecha_str,
                        'tipo': tipo_formateado,
                        'cantidad': cantidad_str,
                        'usuario': m['usuario'],
                        'notas': m['notas'] or '-'
                    })
                except Exception as e:
                    print(f"Error formateando movimiento: {e}")
                    continue
            
            movement_serializer = ProductMovementSerializer(formatted_movements, many=True)
            
            return Response({
                'informacion_general': info_serializer.data,
                'historial_movimientos': movement_serializer.data
            })
        except Exception as e:
            print(f"Error en movements: {e}")
            return Response(
                {'error': f'Error al obtener movimientos: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
