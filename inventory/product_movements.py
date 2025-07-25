from rest_framework import serializers
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Product, FruitLot, MadurationHistory

# Intentar importar los modelos de ventas, con manejo de error si no existen
try:
    from sales.models import Sale, SaleDetail
except ImportError:
    # Definir clases dummy para evitar errores si no existe el módulo
    class Sale:
        pass
    class SaleDetail:
        pass


class ProductMovementSerializer(serializers.Serializer):
    """
    Serializador para representar movimientos de un producto específico
    (entradas, salidas, ajustes, etc.)
    """
    fecha = serializers.DateTimeField()
    tipo = serializers.CharField()
    cantidad = serializers.FloatField()
    usuario = serializers.CharField()
    notas = serializers.CharField(allow_null=True)

    class Meta:
        fields = ('fecha', 'tipo', 'cantidad', 'usuario', 'notas')


class ProductInfoSerializer(serializers.ModelSerializer):
    """
    Serializador para la información general de un producto
    """
    unidad = serializers.CharField(source='get_unidad_display')
    fecha_creacion = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ('uid', 'nombre', 'marca', 'unidad', 'fecha_creacion')
    
    def get_fecha_creacion(self, obj):
        # Obtener la fecha de creación del producto
        if obj.created_at:
            return obj.created_at.strftime("%d %b %Y")
        return None


def get_product_movements(product_id):
    """
    Función para obtener todos los movimientos relacionados con un producto específico.
    Incluye:
    - Entradas (nuevos lotes/pallets)
    - Salidas (ventas)
    - Ajustes (modificaciones de inventario)
    """
    try:
        product = Product.objects.get(uid=product_id)
        movements = []
        
        # 1. Obtener entradas (nuevos lotes/pallets del producto)
        try:
            lotes = FruitLot.objects.filter(producto=product).order_by('fecha_ingreso')
            for lote in lotes:
                try:
                    movements.append({
                        'fecha': lote.fecha_ingreso,
                        'tipo': 'Entrada',
                        'cantidad': float(lote.peso_neto or 0),
                        'usuario': getattr(lote.created_by, 'get_full_name', lambda: 'Sistema')() 
                                if hasattr(lote, 'created_by') and lote.created_by else 'Sistema',
                        'notas': f'Reposición de inventario'
                    })
                except Exception as e:
                    # Si hay error al procesar un lote, continuamos con el siguiente
                    print(f"Error procesando lote: {e}")
                    continue
        except Exception as e:
            print(f"Error obteniendo lotes: {e}")
        
        # 2. Obtener salidas (ventas del producto) - Solo si existe el modelo Sale
        try:
            if 'Sale' in globals() and not isinstance(Sale, type(object)):
                try:
                    ventas = SaleDetail.objects.filter(
                        sale__lote__producto=product
                    ).select_related('sale', 'sale__vendedor').order_by('sale__created_at')
                    
                    for venta in ventas:
                        try:
                            movements.append({
                                'fecha': venta.sale.created_at,
                                'tipo': 'Salida',
                                'cantidad': float(venta.cantidad_kg or 0),
                                'usuario': getattr(venta.sale.vendedor, 'get_full_name', lambda: 'Sistema')() 
                                        if hasattr(venta.sale, 'vendedor') and venta.sale.vendedor else 'Sistema',
                                'notas': f'Venta #{venta.sale.id}'
                            })
                        except Exception as e:
                            print(f"Error procesando venta: {e}")
                            continue
                except Exception as e:
                    print(f"Error obteniendo ventas: {e}")
        except Exception as e:
            print(f"Error al verificar modelo Sale: {e}")
        
        # 3. Obtener ajustes (modificaciones de inventario)
        try:
            for lote in lotes:
                try:
                    if hasattr(lote, 'history'):
                        historical_records = lote.history.all().order_by('history_date')
                        
                        for i, record in enumerate(historical_records):
                            if i > 0:
                                prev_record = historical_records[i-1]
                                
                                # Si hubo un cambio en el peso neto, es un ajuste
                                try:
                                    if record.peso_neto != prev_record.peso_neto:
                                        diferencia = float(record.peso_neto or 0) - float(prev_record.peso_neto or 0)
                                        if diferencia != 0:
                                            movements.append({
                                                'fecha': record.history_date,
                                                'tipo': 'Ajuste',
                                                'cantidad': diferencia,
                                                'usuario': getattr(record.history_user, 'get_full_name', lambda: 'Sistema')() 
                                                        if hasattr(record, 'history_user') and record.history_user else 'Sistema',
                                                'notas': f'Ajuste por inventario'
                                            })
                                except Exception as e:
                                    print(f"Error procesando ajuste: {e}")
                                    continue
                except Exception as e:
                    print(f"Error procesando historial de lote: {e}")
                    continue
        except Exception as e:
            print(f"Error obteniendo ajustes: {e}")
        
        # Ordenar todos los movimientos por fecha (más reciente primero)
        return sorted(movements, key=lambda x: x['fecha'], reverse=True)
    except Product.DoesNotExist:
        return []
    except Exception as e:
        print(f"Error general en get_product_movements: {e}")
        return []
