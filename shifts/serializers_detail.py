from rest_framework import serializers
from django.db.models import Sum, Count, Avg, Q, F, ExpressionWrapper, DecimalField, FloatField
from django.utils import timezone

from .models import Shift, BoxRefill, ShiftExpense, ShiftClosing
from .serializers import ShiftExpenseSerializer
from sales.models import Sale, SalePending, SaleItem
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
    caja_resumen = serializers.SerializerMethodField()
    
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
            'duracion_minutos', 'caja_resumen', 'ventas_resumen', 'ventas_detalle', 
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
        # Ítems de ventas dentro del rango
        items = SaleItem.objects.filter(
            venta__in=ventas
        )

        # Totales
        total_ventas = ventas.count()
        monto_total = ventas.aggregate(total=Sum('total'))['total'] or 0
        total_kg = items.aggregate(total_kg=Sum('peso_vendido'))['total_kg'] or 0
        total_unidades = items.aggregate(total_un=Sum('unidades_vendidas'))['total_un'] or 0
        # Para mantener compatibilidad con nombre previo
        total_cajas = total_unidades

        # Desglose por método de pago (con totales de montos) y métricas por ítems
        ventas_por_metodo = list(ventas.values('metodo_pago').annotate(
            cantidad=Count('id'),
            monto=Sum('total')
        ))
        # Añadir kg y unidades por método de pago usando items
        kg_por_metodo = dict(items.values('venta__metodo_pago').annotate(kg=Sum('peso_vendido')).values_list('venta__metodo_pago', 'kg'))
        un_por_metodo = dict(items.values('venta__metodo_pago').annotate(un=Sum('unidades_vendidas')).values_list('venta__metodo_pago', 'un'))
        for v in ventas_por_metodo:
            metodo = v['metodo_pago']
            v['kg'] = kg_por_metodo.get(metodo, 0) or 0
            v['cajas'] = un_por_metodo.get(metodo, 0) or 0

        # Ventas por vendedor (sumas a nivel de venta e ítems)
        ventas_por_vendedor = list(ventas.values(
            'vendedor__id',
            'vendedor__first_name',
            'vendedor__last_name'
        ).annotate(
            cantidad=Count('id'),
            monto=Sum('total')
        ))
        kg_por_vendedor = dict(items.values('venta__vendedor__id').annotate(kg=Sum('peso_vendido')).values_list('venta__vendedor__id', 'kg'))
        un_por_vendedor = dict(items.values('venta__vendedor__id').annotate(un=Sum('unidades_vendidas')).values_list('venta__vendedor__id', 'un'))
        for v in ventas_por_vendedor:
            vid = v['vendedor__id']
            v['kg'] = kg_por_vendedor.get(vid, 0) or 0
            v['cajas'] = un_por_vendedor.get(vid, 0) or 0
        
        # Productos vendidos (agregar por ítems)
        productos_vendidos = []
        for it in items.select_related('lote__producto', 'venta__cliente'):
            producto = getattr(it.lote, 'producto', None)
            if producto:
                productos_vendidos.append({
                    'id': producto.id,
                    'nombre': getattr(producto, 'nombre', 'Sin producto'),
                    'peso_vendido': it.peso_vendido,
                    'cajas_vendidas': it.unidades_vendidas,
                    'monto': it.subtotal,
                    'fecha_venta': it.created_at,
                    'cliente': it.venta.cliente.nombre if it.venta and it.venta.cliente else 'Cliente ocasional'
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
            # Vendedor
            vendedor_info = None
            if venta.vendedor:
                vendedor_info = {
                    'id': venta.vendedor.id,
                    'nombre': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip()
                }

            # Cliente
            cliente_info = None
            if venta.cliente:
                cliente_info = {
                    'id': venta.cliente.id,
                    'nombre': venta.cliente.nombre,
                    'rut': getattr(venta.cliente, 'rut', None),
                    'telefono': getattr(venta.cliente, 'telefono', None)
                }

            # Ítems de la venta
            items = []
            for it in venta.items.select_related('lote__producto').all():
                lote = it.lote
                lote_info = None
                if lote:
                    lote_info = {
                        'id': lote.id,
                        'uid': getattr(lote, 'uid', None),
                        'qr_code': getattr(lote, 'qr_code', None),
                        'producto': getattr(lote.producto, 'nombre', 'Sin producto') if hasattr(lote, 'producto') else 'Sin producto',
                        'calibre': getattr(lote, 'calibre', None),
                        'categoria': getattr(lote, 'categoria', None)
                    }
                items.append({
                    'id': it.id,
                    'peso_vendido': it.peso_vendido,
                    'unidades_vendidas': it.unidades_vendidas,
                    'precio_kg': it.precio_kg,
                    'precio_unidad': it.precio_unidad,
                    'subtotal': it.subtotal,
                    'lote': lote_info
                })

            detalle_venta = {
                'id': venta.id,
                'codigo_venta': venta.codigo_venta,
                'fecha_venta': venta.created_at,
                'cajas_vendidas': venta.cajas_vendidas,
                'total': venta.total,
                'metodo_pago': venta.metodo_pago,
                'items': items,
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
        
        # Obtener ítems de ventas que afectaron el inventario
        items = SaleItem.objects.filter(
            venta__business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        ).select_related('venta', 'lote__producto')

        # Calcular movimientos de inventario por ventas (a nivel de ítem)
        movimientos_venta = []
        for it in items:
            if it.lote:
                movimientos_venta.append({
                    'tipo': 'venta',
                    'id_venta': it.venta.id if it.venta else None,
                    'lote_id': it.lote.id,
                    'lote_uid': getattr(it.lote, 'uid', None),
                    'lote_qr': getattr(it.lote, 'qr_code', None),
                    'producto': it.lote.producto.nombre if hasattr(it.lote, 'producto') and it.lote.producto else 'Sin producto',
                    'calibre': getattr(it.lote, 'calibre', None),
                    'categoria': getattr(it.lote, 'categoria', None),
                    'peso_vendido': float(it.peso_vendido),
                    'cantidad_cajas': it.unidades_vendidas,
                    'fecha': it.created_at,
                    'vendedor': f"{it.venta.vendedor.first_name} {it.venta.vendedor.last_name}".strip() if it.venta and it.venta.vendedor else 'Sin vendedor',
                    'cliente': it.venta.cliente.nombre if it.venta and it.venta.cliente else 'Cliente ocasional'
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
    
    def get_caja_resumen(self, obj):
        """
        Resumen de caja del turno: ventas y gastos por método, neto, cajas, y comparación con cierre declarado.
        """
        fecha_inicio = obj.fecha_apertura
        fecha_fin = obj.fecha_cierre or timezone.now()

        # Ventas del turno por método
        ventas_qs = Sale.objects.filter(
            business=obj.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin
        )
        ventas_montos = ventas_qs.values('metodo_pago').annotate(monto=Sum('total'))
        ventas_por_metodo = {v['metodo_pago']: float(v['monto'] or 0) for v in ventas_montos}
        total_ventas = float(ventas_qs.aggregate(total=Sum('total'))['total'] or 0)

        # Cajas vendidas estimadas por items
        items_qs = SaleItem.objects.filter(venta__in=ventas_qs)
        cajas_vendidas = int(items_qs.aggregate(total=Sum('unidades_vendidas'))['total'] or 0)

        # Gastos del turno por método
        gastos_qs = ShiftExpense.objects.filter(shift=obj)
        gastos_por_metodo_qs = gastos_qs.values('metodo_pago').annotate(monto=Sum('monto'))
        gastos_por_metodo = {g['metodo_pago']: float(g['monto'] or 0) for g in gastos_por_metodo_qs}
        total_gastos = float(gastos_qs.aggregate(total=Sum('monto'))['total'] or 0)

        # Neto por método
        metodos = set(list(ventas_por_metodo.keys()) + list(gastos_por_metodo.keys()))
        neto_por_metodo = {m: float(ventas_por_metodo.get(m, 0)) - float(gastos_por_metodo.get(m, 0)) for m in metodos}

        # Declarado (solo efectivo) si existe cierre
        declarado = None
        diferencias = None
        diferencia_cajas = None
        explicacion_diferencias = None
        closing = getattr(obj, 'closing', None)
        if closing:
            declarado = {
                'efectivo': float(closing.efectivo_declarado),
                'cajas_contadas': int(closing.cajas_contadas),
                'fecha_cierre_caja': closing.fecha_cierre_caja,
                'cerrado_por': closing.cerrado_por.id,
            }
            # Diferencia solo para efectivo
            efectivo_registrado = float(ventas_por_metodo.get('efectivo', 0)) - float(gastos_por_metodo.get('efectivo', 0))
            diferencias = {
                'efectivo': declarado['efectivo'] - efectivo_registrado,
            }
            diferencia_cajas = declarado['cajas_contadas'] - cajas_vendidas
            explicacion_diferencias = closing.explicacion_diferencias

        return {
            'ventas_por_metodo': ventas_por_metodo,
            'total_ventas': total_ventas,
            'gastos_por_metodo': gastos_por_metodo,
            'total_gastos': total_gastos,
            'neto_por_metodo': neto_por_metodo,
            'cajas_vendidas': cajas_vendidas,
            'declarado': declarado,
            'diferencias': diferencias,
            'diferencia_cajas': diferencia_cajas,
            'explicacion_diferencias': explicacion_diferencias,
        }
     