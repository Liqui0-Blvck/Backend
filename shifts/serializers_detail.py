from rest_framework import serializers
from django.db.models import Sum, Count, Avg, Q, F, ExpressionWrapper, DecimalField, FloatField
from django.utils import timezone

from .models import Shift, BoxRefill, ShiftExpense
from .serializers import ShiftExpenseSerializer
from sales.models import Sale, SalePending
from inventory.models import FruitLot, GoodsReception, ReceptionDetail
from accounts.models import CustomUser, Perfil
from accounts.serializers import CustomUserSerializer
from inventory.serializers import FruitLotSerializer
from notifications.models import Notification

class BoxRefillSerializer(serializers.ModelSerializer):
    """Serializador para los descuentos de cajas por relleno"""
    usuario_nombre = serializers.SerializerMethodField()
    fruit_lot_info = serializers.SerializerMethodField()
    
    class Meta:
        model = BoxRefill
        fields = ['id', 'shift', 'fruit_lot', 'fruit_lot_info', 'cantidad_cajas', 
                 'motivo', 'usuario', 'usuario_nombre', 'fecha', 'business']
    
    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return f"{obj.usuario.first_name} {obj.usuario.last_name}".strip()
        return None
    
    def get_fruit_lot_info(self, obj):
        if obj.fruit_lot:
            return {
                'id': obj.fruit_lot.id,
                'uid': getattr(obj.fruit_lot, 'uid', None),
                'qr_code': getattr(obj.fruit_lot, 'qr_code', None),
                'producto': getattr(obj.fruit_lot.producto, 'nombre', 'Sin producto') if hasattr(obj.fruit_lot, 'producto') else 'Sin producto',
                'calibre': getattr(obj.fruit_lot, 'calibre', None),
                'categoria': getattr(obj.fruit_lot, 'categoria', None)
            }
        return None


class ShiftDetailSerializer(serializers.ModelSerializer):
    """
    Serializador detallado para turnos que incluye información completa
    sobre ventas, movimientos de inventario, transacciones financieras,
    descuentos de cajas por relleno, y todas las actividades ocurridas durante el turno.
    """
    usuario_abre_nombre = serializers.SerializerMethodField()
    usuario_cierra_nombre = serializers.SerializerMethodField()
    duracion_minutos = serializers.SerializerMethodField()
    
    # Resumen de ventas
    ventas_resumen = serializers.SerializerMethodField()
    ventas_detalle = serializers.SerializerMethodField()
    ventas_pendientes = serializers.SerializerMethodField()
    
    # Movimientos de inventario
    movimientos_inventario = serializers.SerializerMethodField()
    recepciones = serializers.SerializerMethodField()
    
    # Descuentos de cajas por relleno
    rellenos_cajas = serializers.SerializerMethodField()
    
    # Gastos del turno
    gastos = serializers.SerializerMethodField()
    
    # Transacciones financieras
    transacciones_financieras = serializers.SerializerMethodField()
    
    
    class Meta:
        model = Shift
        fields = [
            'uid', 'business', 'usuario_abre', 'usuario_cierra', 
            'usuario_abre_nombre', 'usuario_cierra_nombre',
            'fecha_apertura', 'fecha_cierre', 'estado', 'motivo_diferencia',
            'duracion_minutos', 'ventas_resumen', 'ventas_detalle', 
            'ventas_pendientes', 'gastos',
            'movimientos_inventario', 'recepciones', 'rellenos_cajas', 
            'transacciones_financieras'
        ]
    
    def get_usuario_abre_nombre(self, obj):
        if obj.usuario_abre:
            return f"{obj.usuario_abre.first_name} {obj.usuario_abre.last_name}".strip()
        return None
    
    def get_usuario_cierra_nombre(self, obj):
        if obj.usuario_cierra:
            return f"{obj.usuario_cierra.first_name} {obj.usuario_cierra.last_name}".strip()
        return None
    
    def get_duracion_minutos(self, obj):
        if obj.fecha_apertura and obj.fecha_cierre:
            # Calcular la duración en minutos
            delta = obj.fecha_cierre - obj.fecha_apertura
            return int(delta.total_seconds() / 60)
        elif obj.fecha_apertura:
            # Si el turno está abierto, calcular duración hasta ahora
            delta = timezone.now() - obj.fecha_apertura
            return int(delta.total_seconds() / 60)
        return None
    
    def get_ventas_resumen(self, obj):
        """
        Obtiene un resumen detallado de todas las ventas realizadas durante el turno.
        """
        # Definir el rango de fechas del turno
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()
        
        # Obtener todas las ventas realizadas durante el turno
        ventas = Sale.objects.filter(
            business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        )
        
        # Total de ventas
        total_ventas = ventas.count()
        monto_total = ventas.aggregate(total=Sum('total'))['total'] or 0
        total_kg = ventas.aggregate(total_kg=Sum('peso_vendido'))['total_kg'] or 0
        total_cajas = ventas.aggregate(total_cajas=Sum('cajas_vendidas'))['total_cajas'] or 0
        
        # Desglose por método de pago
        ventas_por_metodo = list(ventas.values('metodo_pago').annotate(
            cantidad=Count('id'),
            monto=Sum('total'),
            kg=Sum('peso_vendido'),
            cajas=Sum('cajas_vendidas')
        ))
        
        # Ventas por vendedor
        ventas_por_vendedor = list(ventas.values(
            'vendedor__id',
            'vendedor__first_name',
            'vendedor__last_name'
        ).annotate(
            cantidad=Count('id'),
            monto=Sum('total'),
            kg=Sum('peso_vendido'),
            cajas=Sum('cajas_vendidas')
        ))
        
        # Productos más vendidos
        productos_vendidos = []
        for venta in ventas:
            if hasattr(venta, 'lote') and venta.lote and hasattr(venta.lote, 'producto'):
                producto = venta.lote.producto
                if producto:
                    productos_vendidos.append({
                        'id': producto.id,
                        'nombre': producto.nombre,
                        'peso_vendido': venta.peso_vendido,
                        'cajas_vendidas': venta.cajas_vendidas,
                        'monto': venta.total,
                        'fecha_venta': venta.created_at,
                        'cliente': venta.cliente.nombre if venta.cliente else 'Cliente ocasional'
                    })
        
        # Agrupar por producto para obtener totales
        productos_agrupados = {}
        for p in productos_vendidos:
            key = p['id']
            if key not in productos_agrupados:
                productos_agrupados[key] = {
                    'id': p['id'],
                    'nombre': p['nombre'],
                    'peso_vendido': 0,
                    'cajas_vendidas': 0,
                    'monto': 0,
                    'ventas': []
                }
            productos_agrupados[key]['peso_vendido'] += p['peso_vendido']
            productos_agrupados[key]['cajas_vendidas'] += p['cajas_vendidas']
            productos_agrupados[key]['monto'] += p['monto']
            productos_agrupados[key]['ventas'].append({
                'fecha': p['fecha_venta'],
                'cliente': p['cliente'],
                'peso_vendido': p['peso_vendido'],
                'cajas_vendidas': p['cajas_vendidas'],
                'monto': p['monto']
            })
        
        # Convertir a lista y ordenar por monto
        productos_top = list(productos_agrupados.values())
        productos_top.sort(key=lambda x: x['monto'], reverse=True)
        
        return {
            'total_ventas': total_ventas,
            'monto_total': monto_total,
            'total_kg': total_kg,
            'total_cajas': total_cajas,
            'ventas_por_metodo': ventas_por_metodo,
            'ventas_por_vendedor': ventas_por_vendedor,
            'productos_vendidos': productos_top
        }
        
    def get_ventas_detalle(self, obj):
        """
        Obtiene el detalle completo de todas las ventas realizadas durante el turno.
        """
        # Definir el rango de fechas del turno
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()
        
        # Obtener todas las ventas realizadas durante el turno
        ventas = Sale.objects.filter(
            business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        ).order_by('-created_at')
        
        resultado = []
        for venta in ventas:
            # Obtener información del lote
            lote_info = None
            if hasattr(venta, 'lote') and venta.lote:
                lote = venta.lote
                lote_info = {
                    'id': lote.id,
                    'uid': getattr(lote, 'uid', None),
                    'qr_code': getattr(lote, 'qr_code', None),
                    'producto': getattr(lote.producto, 'nombre', 'Sin producto') if hasattr(lote, 'producto') else 'Sin producto',
                    'calibre': getattr(lote, 'calibre', None),
                    'categoria': getattr(lote, 'categoria', None)
                }
            
            # Obtener información del vendedor
            vendedor_info = None
            if venta.vendedor:
                vendedor_info = {
                    'id': venta.vendedor.id,
                    'nombre': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip()
                }
            
            # Obtener información del cliente
            cliente_info = None
            if venta.cliente:
                cliente_info = {
                    'id': venta.cliente.id,
                    'nombre': venta.cliente.nombre,
                    'rut': getattr(venta.cliente, 'rut', None),
                    'telefono': getattr(venta.cliente, 'telefono', None)
                }
            
            # Construir el detalle de la venta
            detalle_venta = {
                'id': venta.id,
                'fecha_venta': venta.created_at,
                'peso_vendido': venta.peso_vendido,
                'cajas_vendidas': venta.cajas_vendidas,
                'precio_kg': venta.precio_kg,
                'total': venta.total,
                'metodo_pago': venta.metodo_pago,
                'lote': lote_info,
                'vendedor': vendedor_info,
                'cliente': cliente_info,
                'notas': getattr(venta, 'notas', None)
            }
            
            resultado.append(detalle_venta)
        
        return resultado
        
    def get_ventas_pendientes(self, obj):
        """
        Obtiene todas las ventas pendientes creadas durante el turno.
        """
        # Definir el rango de fechas del turno
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()
        
        # Obtener todas las ventas pendientes creadas durante el turno
        ventas_pendientes = SalePending.objects.filter(
            business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        ).order_by('-created_at')
        
        resultado = []
        for venta in ventas_pendientes:
            # Obtener información del lote
            lote_info = None
            if hasattr(venta, 'lote') and venta.lote:
                lote = venta.lote
                lote_info = {
                    'id': lote.id,
                    'uid': getattr(lote, 'uid', None),
                    'qr_code': getattr(lote, 'qr_code', None),
                    'producto': getattr(lote.producto, 'nombre', 'Sin producto') if hasattr(lote, 'producto') else 'Sin producto',
                    'calibre': getattr(lote, 'calibre', None),
                    'categoria': getattr(lote, 'categoria', None)
                }
            
            # Obtener información del vendedor
            vendedor_info = None
            if hasattr(venta, 'vendedor') and venta.vendedor:
                vendedor_info = {
                    'id': venta.vendedor.id,
                    'nombre': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip()
                }
            
            # Obtener información del cliente
            cliente_info = None
            if hasattr(venta, 'cliente') and venta.cliente:
                cliente_info = {
                    'id': venta.cliente.id,
                    'nombre': venta.cliente.nombre,
                    'rut': getattr(venta.cliente, 'rut', None),
                    'telefono': getattr(venta.cliente, 'telefono', None)
                }
            
            # Construir el detalle de la venta pendiente
            detalle_venta = {
                'id': venta.id,
                'uid': venta.uid,   
                'fecha_creacion': venta.created_at,
                'cantidad_kg': getattr(venta, 'peso_vendido', None),
                'cantidad_cajas': getattr(venta, 'cajas_vendidas', None),
                'precio_kg': getattr(venta, 'precio_kg', None),
                'total': getattr(venta, 'total', None),
                'metodo_pago': getattr(venta, 'metodo_pago', None),
                'estado': venta.estado,
                'lote': lote_info,
                'vendedor': vendedor_info,
                'cliente': cliente_info,
                'notas': getattr(venta, 'notas', None)
            }
            
            resultado.append(detalle_venta)
        
        return resultado
    
    def get_movimientos_inventario(self, obj):
        """
        Obtiene un resumen detallado de todos los movimientos de inventario durante el turno.
        """
        # Definir el rango de fechas del turno
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()
        
        # Obtener todas las ventas que afectaron el inventario
        ventas = Sale.objects.filter(
            business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        )
        
        # Calcular movimientos de inventario por ventas
        movimientos_venta = []
        for venta in ventas:
            if hasattr(venta, 'lote') and venta.lote:
                movimientos_venta.append({
                    'tipo': 'venta',
                    'id_venta': venta.id,
                    'lote_id': venta.lote.id,
                    'lote_uid': getattr(venta.lote, 'uid', None),
                    'lote_qr': getattr(venta.lote, 'qr_code', None),
                    'producto': venta.lote.producto.nombre if hasattr(venta.lote, 'producto') and venta.lote.producto else 'Sin producto',
                    'calibre': getattr(venta.lote, 'calibre', None),
                    'categoria': getattr(venta.lote, 'categoria', None),
                    'peso_vendido': float(venta.peso_vendido),
                    'cantidad_cajas': venta.cajas_vendidas,
                    'fecha': venta.created_at,
                    'vendedor': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip() if venta.vendedor else 'Sin vendedor',
                    'cliente': venta.cliente.nombre if venta.cliente else 'Cliente ocasional'
                })
        
        # Obtener los rellenos de cajas realizados durante el turno
        rellenos = BoxRefill.objects.filter(
            business=obj.business,
            shift=obj,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )
        
        # Calcular movimientos de inventario por rellenos de cajas
        movimientos_relleno = []
        for relleno in rellenos:
            if relleno.fruit_lot:
                movimientos_relleno.append({
                    'tipo': 'relleno_cajas',
                    'id_relleno': relleno.id,
                    'lote_id': relleno.fruit_lot.id,
                    'lote_uid': getattr(relleno.fruit_lot, 'uid', None),
                    'lote_qr': getattr(relleno.fruit_lot, 'qr_code', None),
                    'producto': relleno.fruit_lot.producto.nombre if hasattr(relleno.fruit_lot, 'producto') and relleno.fruit_lot.producto else 'Sin producto',
                    'calibre': getattr(relleno.fruit_lot, 'calibre', None),
                    'categoria': getattr(relleno.fruit_lot, 'categoria', None),
                    'cantidad_cajas': relleno.cantidad_cajas,
                    'fecha': relleno.fecha,
                    'usuario': f"{relleno.usuario.first_name} {relleno.usuario.last_name}".strip() if relleno.usuario else 'Sin usuario',
                    'motivo': relleno.motivo
                })
        
        # Combinar todos los movimientos y ordenar por fecha
        todos_movimientos = movimientos_venta + movimientos_relleno
        todos_movimientos.sort(key=lambda x: x['fecha'], reverse=True)
        
        return {
            'movimientos_venta': movimientos_venta,
            'movimientos_relleno': movimientos_relleno,
            'todos_movimientos': todos_movimientos,
            'total_movimientos': len(todos_movimientos),
            'total_kg_vendidos': sum(m['peso_vendido'] for m in movimientos_venta),
            'total_cajas_vendidas': sum(m['cantidad_cajas'] for m in movimientos_venta),
            'total_cajas_relleno': sum(m['cantidad_cajas'] for m in movimientos_relleno)
        }
        
    def get_recepciones(self, obj):
        """
        Obtiene todas las recepciones de mercadería realizadas durante el turno.
        """
        # Definir el rango de fechas del turno
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()
        
        # Obtener todas las recepciones realizadas durante el turno
        recepciones = GoodsReception.objects.filter(
            business=obj.business,
            fecha_recepcion__gte=fecha_inicio,
            fecha_recepcion__lte=fecha_fin
        ).order_by('-fecha_recepcion')
        
        resultado = []
        for recepcion in recepciones:
            # Obtener detalles de la recepción
            detalles = []
            if hasattr(recepcion, 'detalles'):
                for detalle in recepcion.detalles.all():
                    detalles.append({
                        'id': detalle.id,
                        'producto': detalle.producto.nombre if hasattr(detalle, 'producto') and detalle.producto else 'Sin producto',
                        'cantidad_cajas': detalle.cantidad_cajas,
                        'peso_bruto': float(detalle.peso_bruto),
                        'peso_neto': float(detalle.peso_neto),
                        'costo': float(detalle.costo),
                        'calibre': detalle.calibre or 'N/A',
                        'variedad': detalle.variedad or 'N/A'
                    })
            
            # Obtener información del receptor y revisor
            receptor_info = None
            if hasattr(recepcion, 'receptor') and recepcion.receptor:
                receptor_info = {
                    'id': recepcion.receptor.id,
                    'nombre': f"{recepcion.receptor.first_name} {recepcion.receptor.last_name}".strip()
                }
            
            revisor_info = None
            if hasattr(recepcion, 'revisor') and recepcion.revisor:
                revisor_info = {
                    'id': recepcion.revisor.id,
                    'nombre': f"{recepcion.revisor.first_name} {recepcion.revisor.last_name}".strip()
                }
            
            # Construir el detalle de la recepción
            detalle_recepcion = {
                'id': recepcion.id,
                'fecha_recepcion': recepcion.fecha_recepcion,
                'proveedor': recepcion.proveedor.nombre if hasattr(recepcion, 'proveedor') and recepcion.proveedor else 'Sin proveedor',
                'numero_guia': getattr(recepcion, 'numero_guia', None),
                'total': getattr(recepcion, 'total', None),
                'receptor': receptor_info,
                'revisor': revisor_info,
                'detalles': detalles,
                'notas': getattr(recepcion, 'notas', None)
            }
            
            resultado.append(detalle_recepcion)
        
        return resultado
        
    def get_rellenos_cajas(self, obj):
        """
        Obtiene todos los descuentos de cajas por concepto de relleno realizados durante el turno.
        """
        # Obtener todos los rellenos de cajas del turno
        rellenos = BoxRefill.objects.filter(
            shift=obj
        ).order_by('-fecha')
        
        return BoxRefillSerializer(rellenos, many=True).data
        
    def get_gastos(self, obj):
        """
        Obtiene todos los gastos incurridos durante el turno.
        """
        # Obtener todos los gastos del turno
        gastos = ShiftExpense.objects.filter(
            shift=obj
        ).order_by('-fecha')
        
        # Serializar los gastos
        gastos_data = ShiftExpenseSerializer(gastos, many=True).data
        
        # Calcular totales por categoría
        categorias = {}
        for gasto in gastos:
            categoria = gasto.get_categoria_display()
            if categoria not in categorias:
                categorias[categoria] = 0
            categorias[categoria] += float(gasto.monto)
        
        # Calcular totales por método de pago
        metodos_pago = {}
        for gasto in gastos:
            metodo = gasto.get_metodo_pago_display()
            if metodo not in metodos_pago:
                metodos_pago[metodo] = 0
            metodos_pago[metodo] += float(gasto.monto)
        
        # Calcular total general
        total_gastos = sum(float(gasto.monto) for gasto in gastos)
        
        return {
            'saldo': obj.saldo_inicial,
            'gastos': gastos_data,
            'total_gastos': total_gastos,
            'gastos_por_categoria': [{'categoria': k, 'monto': v} for k, v in categorias.items()],
            'gastos_por_metodo_pago': [{'metodo': k, 'monto': v} for k, v in metodos_pago.items()],
            'cantidad_gastos': len(gastos)
        }

    def get_transacciones_financieras(self, obj):
        """
        Obtiene un resumen detallado de todas las transacciones financieras durante el turno.
        """
        # Definir el rango de fechas del turno
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()
        
        # Obtener todas las ventas con sus pagos
        ventas = Sale.objects.filter(
            business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        )
        
        # Calcular ingresos por ventas
        ingresos_ventas = ventas.aggregate(total=Sum('total'))['total'] or 0
        
        # Desglose por método de pago
        ingresos_por_metodo = list(ventas.values('metodo_pago').annotate(
            cantidad=Count('id'),
            monto=Sum('total')
        ))
        
        # Calcular gastos por rellenos de cajas
        rellenos = BoxRefill.objects.filter(
            business=obj.business,
            shift=obj,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )
        
        # Aquí se podría calcular el costo de los rellenos si se tuviera un precio por caja
        # Por ahora, solo contamos la cantidad de cajas
        total_cajas_relleno = rellenos.aggregate(total=Sum('cantidad_cajas'))['total'] or 0
        
        # Obtener todos los gastos del turno
        gastos = ShiftExpense.objects.filter(
            shift=obj
        )
        
        # Calcular total de gastos
        total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or 0
        
        # Desglose por categoría de gasto
        gastos_por_categoria = list(gastos.values('categoria').annotate(
            cantidad=Count('id'),
            monto=Sum('monto')
        ))
        
        # Calcular balance de caja (ingresos - gastos)
        balance_caja = float(ingresos_ventas) - float(total_gastos)
        
        # Construir detalle de transacciones
        detalle_transacciones = [
            {
                'tipo': 'ingreso',
                'concepto': 'Ventas',
                'monto': ingresos_ventas
            }
        ]
        
        # Agregar gastos al detalle de transacciones
        for gasto in gastos:
            detalle_transacciones.append({
                'tipo': 'gasto',
                'concepto': f"{gasto.get_categoria_display()}: {gasto.descripcion}",
                'monto': -float(gasto.monto)  # Negativo porque es un gasto
            })
        
        # Ordenar transacciones por fecha
        detalle_transacciones.sort(key=lambda x: x['monto'], reverse=True)
        
        return {
            'ingresos_totales': ingresos_ventas,
            'ingresos_por_metodo': ingresos_por_metodo,
            'gastos_totales': total_gastos,
            'gastos_por_categoria': gastos_por_categoria,
            'total_cajas_relleno': total_cajas_relleno,
            'balance_caja': balance_caja,
            'detalle_transacciones': detalle_transacciones,
        }
        
        # # Agregar ventas por usuario
        # for venta in ventas_por_usuario:
        #     user_id = venta['vendedor__id']
        #     if user_id not in usuarios_activos:
        #         usuarios_activos[user_id] = {
        #             'id': user_id,
        #             'username': venta['vendedor__username'],
        #             'nombre': f"{venta['vendedor__first_name']} {venta['vendedor__last_name']}".strip() or venta['vendedor__username'],
        #             'ventas_count': 0,
        #             'ventas_monto': 0,
        #             'ventas_kg': 0,
        #             'ventas_cajas': 0,
        #             'rellenos_count': 0,
        #             'rellenos_cajas': 0
        #         }
        #     usuarios_activos[user_id]['ventas_count'] = venta['ventas_count']
        #     usuarios_activos[user_id]['ventas_monto'] = venta['ventas_monto']
        #     usuarios_activos[user_id]['ventas_kg'] = venta['ventas_kg']
        #     usuarios_activos[user_id]['ventas_cajas'] = venta['ventas_cajas']
        
        # # Agregar rellenos por usuario
        # for relleno in rellenos_por_usuario:
        #     user_id = relleno['usuario__id']
        #     if user_id not in usuarios_activos:
        #         usuarios_activos[user_id] = {
        #             'id': user_id,
        #             'username': relleno['usuario__username'],
        #             'nombre': f"{relleno['usuario__first_name']} {relleno['usuario__last_name']}".strip() or relleno['usuario__username'],
        #             'ventas_count': 0,
        #             'ventas_monto': 0,
        #             'ventas_kg': 0,
        #             'ventas_cajas': 0,
        #             'rellenos_count': 0,
        #             'rellenos_cajas': 0
        #         }
        #     usuarios_activos[user_id]['rellenos_count'] = relleno['rellenos_count']
        #     usuarios_activos[user_id]['rellenos_cajas'] = relleno['rellenos_cajas']
        
        # # Convertir a lista y ordenar por actividad total
        # usuarios_lista = list(usuarios_activos.values())
        # usuarios_lista.sort(key=lambda x: (x['ventas_count'] + x['rellenos_count']), reverse=True)
        
        # return {
        #     'usuarios_activos': usuarios_lista,
        #     'total_usuarios_activos': len(usuarios_lista)
        # }
     