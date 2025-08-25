from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from datetime import timedelta, time, datetime
import datetime as dt
from django.utils import timezone
from django.db.models import Sum, Count, F, Q, DecimalField, FloatField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek, Coalesce
from django.utils.dateparse import parse_date
from accounts.models import Perfil

# Importaciones de modelos
from sales.models import Sale, SaleItem, SalePendingItem
from inventory.models import FruitLot, StockReservation, Product
from shifts.models import Shift

# Importaciones de utilidades
from scripts.maduration_pricing import calculate_maduration_price

def _get_business_from_user(user):
    """Obtiene el negocio desde el usuario o su perfil de forma segura."""
    # Acceso directo
    if hasattr(user, 'business') and user.business:
        return user.business
    # Perfil relacionado
    perfil = getattr(user, 'perfil', None)
    if perfil and getattr(perfil, 'business', None):
        return perfil.business
    # Lookup explícito por si la relación no está en cache
    try:
        perfil = Perfil.objects.get(user=user)
        return getattr(perfil, 'business', None)
    except Perfil.DoesNotExist:
        return None


class ReportSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsSameBusiness]
    def get(self, request):
        user = request.user
        business = _get_business_from_user(request.user)
        if not business:
            return Response({'detail': 'Usuario no tiene un negocio asociado.'}, status=404)
        
        # Determinar si es proveedor y obtener su proveedor vinculado
        is_proveedor = request.user.groups.filter(name='Proveedor').exists()
        proveedor = None
        if is_proveedor:
            perfil = getattr(user, 'perfil', None)
            proveedor = getattr(perfil, 'proveedor', None) if perfil else None
            if not proveedor:
                return Response({'detail': 'Proveedor no vinculado al usuario.'}, status=404)
        
        # Resumen por períodos (hoy, esta semana, este mes, total)
        
        # Fechas de referencia
        hoy = timezone.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)
        
        # Rangos de fechas
        rango_hoy = (datetime.combine(hoy, time.min), datetime.combine(hoy, time.max))
        rango_semana = (datetime.combine(inicio_semana, time.min), datetime.combine(hoy, time.max))
        rango_mes = (datetime.combine(inicio_mes, time.min), datetime.combine(hoy, time.max))
        
        # Helper para calcular métricas por período considerando ambos tipos de productos
        def calcular_metricas(qs_ventas):
            total_ventas = qs_ventas.count()
            ingresos = qs_ventas.aggregate(total=Sum('total'))['total'] or 0
            # Paltas por kg
            kg_paltas = SaleItem.objects.filter(
                venta__in=qs_ventas,
                lote__producto__tipo_producto='palta'
            ).aggregate(total=Sum('peso_vendido'))['total'] or 0
            # Otros por unidades
            unidades_otros = SaleItem.objects.filter(
                venta__in=qs_ventas,
                lote__producto__tipo_producto='otro'
            ).aggregate(total=Sum('unidades_vendidas'))['total'] or 0
            return {
                'total_ventas': total_ventas,
                'total_ingresos': ingresos,
                # Backward-compatible keys
                'total_kg': kg_paltas,
                'total_cajas': unidades_otros,
                # Detailed keys
                'total_kg_paltas': kg_paltas,
                'total_unidades_otros': unidades_otros,
            }

        # Helper para aplicar filtro por proveedor a ventas
        def ventas_filtradas_por_proveedor(qs):
            if not is_proveedor:
                return qs
            return qs.filter(
                Q(items__lote__proveedor=proveedor) |
                Q(items__proveedor_original=proveedor) |
                Q(items__lote__propietario_original=proveedor)
            ).distinct()

        # Ventas de hoy
        ventas_hoy = ventas_filtradas_por_proveedor(
            Sale.objects.filter(business=business, cancelada=False, created_at__range=rango_hoy)
        )
        m_hoy = calcular_metricas(ventas_hoy)

        # Ventas de esta semana
        ventas_semana = ventas_filtradas_por_proveedor(
            Sale.objects.filter(business=business, cancelada=False, created_at__range=rango_semana)
        )
        m_semana = calcular_metricas(ventas_semana)

        # Ventas de este mes
        ventas_mes = ventas_filtradas_por_proveedor(
            Sale.objects.filter(business=business, cancelada=False, created_at__range=rango_mes)
        )
        m_mes = calcular_metricas(ventas_mes)

        # Total histórico
        ventas_total = ventas_filtradas_por_proveedor(
            Sale.objects.filter(business=business, cancelada=False)
        )
        m_hist = calcular_metricas(ventas_total)
        
        # Resumen de inventario
        
        # Total de inventario
        lotes = FruitLot.objects.filter(business=business)
        if is_proveedor:
            lotes = lotes.filter(Q(proveedor=proveedor) | Q(propietario_original=proveedor))
        total_lotes = lotes.count()
        total_kg_stock = lotes.aggregate(total=Sum('peso_neto'))['total'] or 0
        
        # Obtener reservas por lote
        reservas = StockReservation.objects.filter(
            lote__business=business
        ).values('lote').annotate(
            total_reservado=Sum('kg_reservados')
        )
        
        reservas_dict = {item['lote']: item['total_reservado'] for item in reservas}
        
        # Calcular peso disponible
        total_kg_reservado = sum(reservas_dict.values())
        total_kg_disponible = total_kg_stock - total_kg_reservado
        
        # Valor estimado del inventario
        valor_inventario = 0
        for lote in lotes:
            if lote.peso_neto:
                valor_inventario += lote.peso_neto * lote.costo_actualizado()
        
        # Últimos 5 productos con menos stock
        productos = Product.objects.filter(business=business)
        
        productos_bajo_stock = []
        for producto in productos:
            lotes_producto = lotes.filter(producto=producto)
            peso_total = lotes_producto.aggregate(total=Sum('peso_neto'))['total'] or 0
            
            # Calcular reservas
            reservas_producto = 0
            for lote in lotes_producto:
                # reservas_dict está indexado por ID de lote (values('lote')), no por UID
                reservas_producto += reservas_dict.get(lote.id, 0) or 0
            
            disponible = peso_total - reservas_producto
            
            productos_bajo_stock.append({
                'uid': producto.uid,
                'nombre': producto.nombre,
                'peso_total': peso_total,
                'peso_disponible': disponible
            })
        
        # Ordenar por disponibilidad ascendente y tomar los 5 primeros
        productos_bajo_stock.sort(key=lambda x: x['peso_disponible'])
        productos_bajo_stock = productos_bajo_stock[:5]
        
        # Información de turnos
        # Para proveedores, ocultar información de turnos
        if is_proveedor:
            turno_activo = None
            turno_usuario = None
            ultimos_turnos = []
        else:
            # Verificar turno activo
            turno_activo = Shift.objects.filter(
                business=business,
                estado="abierto"
            ).first()
            
            turno_usuario = Shift.objects.filter(
                business=business,
                usuario_abre=user,
                estado="abierto"
            ).first()
            
            # Últimos 3 turnos
            ultimos_turnos = Shift.objects.filter(
                business=business
            ).order_by('-fecha_apertura')[:3]
        
        ultimos_turnos_data = []
        for turno in ultimos_turnos:
            usuario_nombre = f"{turno.usuario_abre.first_name} {turno.usuario_abre.last_name}".strip() or turno.usuario_abre.username
            
            # Calcular ventas en el turno
            if turno.estado == "cerrado" and turno.fecha_cierre:
                ventas_turno = ventas_filtradas_por_proveedor(
                    Sale.objects.filter(
                        business=business,
                        created_at__range=[turno.fecha_apertura, turno.fecha_cierre]
                    )
                )
            else:
                ventas_turno = ventas_filtradas_por_proveedor(
                    Sale.objects.filter(
                        business=business,
                        created_at__gte=turno.fecha_apertura
                    )
                )
            
            total_ventas_turno = ventas_turno.count()
            total_ingresos_turno = ventas_turno.annotate(
                subtotal=Sum(F('items__peso_vendido') * F('items__precio_kg'), output_field=DecimalField())
            ).aggregate(total=Sum('subtotal'))['total'] or 0
            
            ultimos_turnos_data.append({
                'usuario_nombre': usuario_nombre,
                'fecha_apertura': turno.fecha_apertura,
                'fecha_cierre': turno.fecha_cierre,
                'estado': turno.estado,
                'total_ventas': total_ventas_turno,
                'total_ingresos': total_ingresos_turno
            })
        
        return Response({
            'fecha_actual': hoy,
            'ventas': {
                'hoy': m_hoy,
                'semana': m_semana,
                'mes': m_mes,
                'historico': m_hist,
            },
            'inventario': {
                'total_lotes': total_lotes,
                'total_kg': total_kg_stock,
                'total_kg_disponible': total_kg_disponible,
                'total_kg_reservado': total_kg_reservado,
                'valor_estimado': valor_inventario,
                'productos_bajo_stock': productos_bajo_stock
            },
            'turnos': {
                'hay_turno_activo': turno_activo is not None,
                'usuario_tiene_turno': turno_usuario is not None,
                'ultimos_turnos': ultimos_turnos_data
            }
        })

class StockReportView(APIView):
    permission_classes = [IsAuthenticated, IsSameBusiness]
    
    def get(self, request, format=None):
        # Función para redondear valores numéricos a 2 decimales
        def redondear(valor):
            if isinstance(valor, (int, float)):
                return round(valor, 2)
            return valor

        # Obtener el negocio del usuario mediante helper
        business = _get_business_from_user(request.user)
        if not business:
            return Response({'detail': 'Usuario no tiene un negocio asociado.'}, status=404)
        
        # Verificar si el usuario es admin o supervisor para mostrar información sensible
        es_admin_o_supervisor = request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists()

        # Obtener parámetros de filtrado
        producto_id = request.query_params.get('producto_id')
        nombre_producto = request.query_params.get('nombre_producto', '').lower()
        calibre = request.query_params.get('calibre')
        box_type_id = request.query_params.get('box_type_id')
        pallet_id = request.query_params.get('pallet_id')
        lote_detalle_id = request.query_params.get('lote_detalle_id')
        tipo_producto = request.query_params.get('tipo_producto', '').lower()
        
        # Procesar parámetros de fecha
        try:
            fecha_inicio_str = request.query_params.get('fecha_inicio')
            fecha_fin_str = request.query_params.get('fecha_fin')
            
            if fecha_inicio_str:
                fecha_inicio = dt.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            else:
                fecha_inicio = timezone.now().date()
                
            if fecha_fin_str:
                fecha_fin = dt.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            else:
                fecha_fin = timezone.now().date()
        except (ValueError, TypeError):
            # Si hay error en el formato de fechas, usar fecha actual
            fecha_inicio = timezone.now().date()
            fecha_fin = timezone.now().date()

        # Procesar el parámetro tipo_producto para permitir búsqueda por nombre específico
        if tipo_producto:
            # Si es uno de los tipos especiales, se aplicará el filtro correspondiente
            if tipo_producto not in ['paltas', 'otros']:
                # Si no es un tipo especial, lo tratamos como nombre de producto
                nombre_producto = tipo_producto
                # Limpiamos tipo_producto para evitar conflictos en los filtros
                tipo_producto = None

        # Base del queryset - todos los lotes del negocio
        queryset = FruitLot.objects.filter(
            business=business
        ).select_related('producto', 'box_type', 'pallet_type')
        
        # Verificar si hay un filtro específico por estado_lote
        estado_lote = request.query_params.get('estado_lote', None)
        
        # Si se solicita específicamente un estado, aplicar ese filtro
        if estado_lote is not None:
            queryset = queryset.filter(estado_lote=estado_lote)
        else:
            # Si no hay filtro específico, ocultar los lotes agotados por defecto
            queryset = queryset.exclude(estado_lote='agotado')
        
        # Excluir lotes que tienen ventas pendientes asociadas
        from sales.models import SalePending
        lotes_con_ventas_pendientes = SalePending.objects.filter(estado='pendiente').values_list('lote', flat=True)
        queryset = queryset.exclude(id__in=lotes_con_ventas_pendientes)
        
        # Aplicar filtros
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)
        
        # Filtrar por nombre de producto
        if nombre_producto:
            queryset = queryset.filter(producto__nombre__icontains=nombre_producto)
            
        if calibre:
            queryset = queryset.filter(calibre=calibre)
        
        # Filtrar por tipo de producto (categorías especiales) usando campo tipo_producto
        if tipo_producto == 'paltas':
            queryset = queryset.filter(producto__tipo_producto='palta')
        elif tipo_producto == 'otros':
            queryset = queryset.filter(producto__tipo_producto='otro')
        
        # Filtrar por nombre específico de producto (ya aplicado arriba, eliminamos duplicación)

        # Obtener reservas por lote
        reservas = StockReservation.objects.filter(
            lote__business=business
        ).values('lote').annotate(
            total_reservado=Sum('kg_reservados')
        )
        
        # Crear un diccionario para acceso rápido
        reservas_dict = {item['lote']: item.get('total_reservado', 0) for item in reservas}
        
        # Procesar resultados
        resultados = []
        for lote in queryset:
            # Calcular peso disponible (peso neto - reservado)
            reservado = float(reservas_dict.get(lote.id, 0) or 0)
            disponible = float(lote.peso_neto) - reservado if lote.peso_neto else 0
            
            # Detectar tipo de producto
            nombre_producto = lote.producto.nombre.lower()
            es_palta = 'palta' in nombre_producto or 'aguacate' in nombre_producto
            es_mango = 'mango' in nombre_producto
            es_platano = 'platano' in nombre_producto or 'plátano' in nombre_producto or 'banano' in nombre_producto
            
            # Determinar tipo de producto para mostrar información específica
            tipo_producto = 'otro'
            if es_palta:
                tipo_producto = 'palta'
            elif es_mango:
                tipo_producto = 'mango'
            elif es_platano:
                tipo_producto = 'platano'
            
            # Calcular días desde ingreso
            dias_desde_ingreso = (timezone.now().date() - lote.fecha_ingreso).days if lote.fecha_ingreso else 0
            
            # Inicializa datos base del lote usando el serializer (siempre actualizado)
            from inventory.serializers import FruitLotSerializer
            lote_data = FruitLotSerializer(lote).data
            
            # Asegurarse de que el estado de maduración se tome directamente del modelo
            # para evitar cualquier discrepancia con la serialización
            if hasattr(lote, 'estado_maduracion') and lote.estado_maduracion:
                lote_data['estado_maduracion'] = lote.estado_maduracion

            # Cálculos manuales y agregados (mantén toda la lógica original)
            # reservas_dict está indexado por ID de lote (values('lote'))
            reservado = float(reservas_dict.get(lote.id, 0) or 0)
            disponible = float(lote_data.get('peso_neto', 0) or 0) - reservado if lote_data.get('peso_neto') else 0

            # Detectar tipo de producto
            nombre_producto = lote_data.get('producto_nombre', '').lower()
            es_palta = 'palta' in nombre_producto or 'aguacate' in nombre_producto
            es_mango = 'mango' in nombre_producto
            es_platano = 'platano' in nombre_producto or 'plátano' in nombre_producto or 'banano' in nombre_producto

            tipo_producto = 'otro'
            if es_palta:
                tipo_producto = 'palta'
            elif es_mango:
                tipo_producto = 'mango'
            elif es_platano:
                tipo_producto = 'platano'

            # Asegura que fecha_ingreso sea date para evitar errores de tipo
            fecha_ingreso = lote_data.get('fecha_ingreso')
            if fecha_ingreso:
                if isinstance(fecha_ingreso, str):
                    from datetime import datetime
                    try:
                        fecha_ingreso_dt = datetime.strptime(fecha_ingreso, "%Y-%m-%d").date()
                    except ValueError:
                        # Intenta con formato datetime completo si aplica
                        try:
                            fecha_ingreso_dt = datetime.strptime(fecha_ingreso, "%Y-%m-%dT%H:%M:%S.%fZ").date()
                        except Exception:
                            fecha_ingreso_dt = timezone.now().date()
                else:
                    fecha_ingreso_dt = fecha_ingreso
                dias_desde_ingreso = (timezone.now().date() - fecha_ingreso_dt).days
            else:
                dias_desde_ingreso = 0

            # Calcular valor total según tipo de producto
            if es_mango or es_platano:
                valor_total = float(lote_data.get('costo_actualizado', 0) or 0) * float(lote_data.get('cantidad_cajas', 0) or 0)
            else:
                valor_total = float(lote_data.get('peso_neto', 0) or 0) * float(lote_data.get('costo_actualizado', 0) or 0)

            # Actualiza/agrega los campos calculados y manuales
            lote_data.update({
                'peso_reservado': reservado,
                'peso_disponible': disponible,
                'valor_total': valor_total,
                'tipo_producto': tipo_producto,
                'es_palta': es_palta,
                'es_mango': es_mango,
                'es_platano': es_platano,
                'dias_desde_ingreso': dias_desde_ingreso,
                'tiene_detalle_maduracion': es_palta,
                'mostrar_detalle': str(lote_data['uid']) == lote_detalle_id,
            })

            
            # Agregar información específica según el tipo de producto
            if tipo_producto == 'palta':
                # Verificar el estado inicial registrado en la base de datos
                estado_inicial = lote.estado_maduracion if hasattr(lote, 'estado_maduracion') else 'verde'
                
                # Calcular la progresión de maduración basada en días y estado inicial
                # Definir los estados de maduración en orden progresivo
                estados = ['verde', 'pre-maduro', 'maduro', 'sobremaduro']
                
                # Encontrar el índice del estado inicial
                indice_inicial = estados.index(estado_inicial) if estado_inicial in estados else 0
                
                # Calcular avance adicional basado en días
                avance_adicional = 0
                if dias_desde_ingreso >= 15:
                    avance_adicional = 3  # Avanza hasta sobremaduro
                elif dias_desde_ingreso >= 10:
                    avance_adicional = 2  # Avanza hasta maduro
                elif dias_desde_ingreso >= 5:
                    avance_adicional = 1  # Avanza hasta pre-maduro
                
                # Calcular el nuevo índice, asegurándose de no exceder el máximo
                indice_final = min(indice_inicial + avance_adicional, len(estados) - 1)
                
                # Obtener el estado de maduración final
                estado_maduracion = estados[indice_final]
                
                # Calcular pérdida estimada basada en estado de maduración
                porcentaje_perdida = 0
                if estado_maduracion == 'verde':
                    porcentaje_perdida = 2
                elif estado_maduracion == 'pre-maduro':
                    porcentaje_perdida = 3
                elif estado_maduracion == 'maduro':
                    porcentaje_perdida = 5
                elif estado_maduracion == 'sobremaduro':
                    porcentaje_perdida = 10
                
                # Calcular pérdida en kg y valor monetario
                peso_neto = float(lote.peso_neto or 0)
                factor_perdida = porcentaje_perdida / 100
                perdida_estimada = peso_neto * factor_perdida
                disponible_float = float(disponible)
                peso_vendible = disponible_float - perdida_estimada if disponible_float > perdida_estimada else 0
                costo_actual = float(lote.costo_actualizado() or 0)
                valor_perdida = perdida_estimada * costo_actual
                
                # Obtener precio recomendado
                precio_recomendado = 0
                costo_real_kg = 0
                ganancia_kg = 0
                margen = 0
                
                # El costo real por kg es directamente el costo inicial de la fruta
                # Este es el valor base que se actualiza según el nivel de maduración
                costo_real_kg = float(lote.costo_inicial) if lote.costo_inicial else 0
                
                # Calcular precio recomendado con un margen del 30%
                precio_recomendado = costo_real_kg * 1.3
                
                # Calcular ganancia y margen
                ganancia_kg = precio_recomendado - costo_real_kg
                margen = (ganancia_kg / costo_real_kg * 100) if costo_real_kg > 0 else 25.0
                
                # Calcular ingresos y ganancias estimadas
                ingreso_estimado = precio_recomendado * peso_vendible
                ganancia_total = ganancia_kg * peso_vendible
                
                # Agregar datos de maduración al lote
                lote_data['estado_maduracion'] = estado_maduracion
                lote_data['dias_en_bodega'] = dias_desde_ingreso
                lote_data['porcentaje_perdida'] = porcentaje_perdida
                lote_data['perdida_estimada'] = redondear(perdida_estimada)
                lote_data['valor_perdida'] = redondear(valor_perdida)
                lote_data['peso_vendible'] = redondear(peso_vendible)
                lote_data['precio_recomendado_kg'] = redondear(precio_recomendado)
                lote_data['costo_real_kg'] = redondear(costo_real_kg)
                lote_data['ganancia_kg'] = redondear(ganancia_kg)
                lote_data['margen'] = redondear(margen)
                lote_data['ingreso_estimado'] = redondear(ingreso_estimado)
                lote_data['ganancia_total'] = redondear(ganancia_total)
                
                # Añadir resumen para paltas con precios realistas (en pesos chilenos)
                lote_data['resumen_producto'] = f"Palta {lote.calibre if lote.calibre else 'S/C'} | ${redondear(costo_real_kg):,.0f}/kg | ${redondear(precio_recomendado):,.0f}/kg rec. | {estado_maduracion.capitalize()}"
                
                # Calcular urgencia de venta
                urgencia_venta = 'baja'
                if estado_maduracion == 'maduro':
                    urgencia_venta = 'alta'
                elif estado_maduracion == 'sobremaduro':
                    urgencia_venta = 'critica'
                
                lote_data['urgencia_venta'] = urgencia_venta
                
                # Calcular días para venta óptima
                dias_venta_optima = 0
                if estado_maduracion == 'verde':
                    dias_venta_optima = 5
                elif estado_maduracion == 'pre-maduro':
                    dias_venta_optima = 2
                
                # Calcular proyección de maduración
                dias_para_maduro = max(0, 10 - dias_desde_ingreso)
                dias_para_sobremaduro = max(0, 15 - dias_desde_ingreso)
                perdida_adicional_3dias = peso_neto * 0.03  # 3% adicional en 3 días
                perdida_adicional_5dias = peso_neto * 0.06  # 6% adicional en 5 días
                
                lote_data['proyeccion_maduracion'] = {
                    'dias_para_maduro': dias_para_maduro,
                    'dias_para_sobremaduro': dias_para_sobremaduro,
                    'perdida_adicional_3dias': redondear(perdida_adicional_3dias),
                    'perdida_adicional_5dias': redondear(perdida_adicional_5dias)
                }
                
                # Calcular escenarios de precio
                escenarios_precio = []
                if precio_recomendado > 0:
                    for ajuste, factor in [('-10%', 0.9), ('-5%', 0.95), ('+5%', 1.05), ('+10%', 1.1)]:
                        precio_ajustado = precio_recomendado * factor
                        ganancia_ajustada = precio_ajustado - costo_real_kg
                        margen_ajustado = (ganancia_ajustada / precio_ajustado) * 100 if precio_ajustado > 0 else 0
                        
                        escenarios_precio.append({
                            'ajuste': ajuste,
                            'precio': redondear(precio_ajustado),
                            'ganancia': redondear(ganancia_ajustada),
                            'margen': redondear(margen_ajustado),
                            'ingreso_total': redondear(precio_ajustado * peso_vendible),
                            'ganancia_total': redondear(ganancia_ajustada * peso_vendible)
                        })
                
                lote_data['escenarios_precio'] = escenarios_precio
                
                # Recomendaciones basadas en el estado
                if estado_maduracion == 'verde':
                    lote_data['recomendacion'] = {
                        'accion': 'esperar',
                        'mensaje': 'Mantener en cámara de maduración controlada. Revisar en 3 días.',
                        'precio_sugerido': redondear(precio_recomendado)
                    }
                elif estado_maduracion == 'pre-maduro':
                    lote_data['recomendacion'] = {
                        'accion': 'preparar',
                        'mensaje': 'Monitorear diariamente. Preparar para distribución en 2 días.',
                        'precio_sugerido': redondear(precio_recomendado)
                    }
                elif estado_maduracion == 'maduro':
                    lote_data['recomendacion'] = {
                        'accion': 'vender',
                        'mensaje': f'Priorizar para venta inmediata. Precio óptimo: ${redondear(precio_recomendado)}/kg',
                        'precio_sugerido': redondear(precio_recomendado)
                    }
                elif estado_maduracion == 'sobremaduro':
                    descuento_recomendado = 15 if dias_desde_ingreso <= 17 else 30
                    precio_descuento = precio_recomendado * (1 - descuento_recomendado/100)
                    lote_data['recomendacion'] = {
                        'accion': 'liquidar',
                        'mensaje': f'Vender con {descuento_recomendado}% de descuento (${redondear(precio_descuento)}/kg) o procesar para productos derivados',
                        'precio_sugerido': redondear(precio_descuento)
                    }
            
            # Información específica para mangos
            elif tipo_producto == 'mango' and es_admin_o_supervisor:
                try:
                    # Para mangos, el calibre es la cantidad de mangos por caja
                    calibre_num = int(lote.calibre) if lote.calibre and lote.calibre.isdigit() else 0
                    
                    # El costo por caja es el costo_actualizado (ya viene por caja)
                    costo_por_caja = float(lote.costo_actualizado() or 0)
                    
                    # Calcular peso por mango
                    peso_por_mango = lote.peso_neto / (calibre_num * lote.cantidad_cajas) if calibre_num > 0 and lote.cantidad_cajas and lote.cantidad_cajas > 0 else 0
                    
                    # Calcular costo por mango
                    costo_por_mango = costo_por_caja / calibre_num if calibre_num > 0 else 0
                    
                    # Calcular precio recomendado con margen del 30%
                    margen_deseado = 0.30  # 30% de margen
                    precio_recomendado_mango = costo_por_mango / (1 - margen_deseado) if margen_deseado < 1 else 0
                    precio_recomendado_caja = costo_por_caja / (1 - margen_deseado) if margen_deseado < 1 else 0
                    
                    # Calcular precio por kg (solo para referencia)
                    peso_por_caja = float(lote.peso_neto) / float(lote.cantidad_cajas) if lote.cantidad_cajas and lote.cantidad_cajas > 0 else 0
                    precio_recomendado_kg = precio_recomendado_caja / peso_por_caja if peso_por_caja > 0 else 0
                    costo_kg = costo_por_caja / peso_por_caja if peso_por_caja > 0 else 0
                    
                    # Calcular ganancia y margen
                    ganancia_por_caja = precio_recomendado_caja - costo_por_caja
                    ganancia_total = ganancia_por_caja * float(lote.cantidad_cajas or 0)
                    
                    # Agregar información específica de mangos
                    lote_data['mangos_por_caja'] = calibre_num
                    lote_data['peso_por_mango'] = redondear(peso_por_mango)
                    lote_data['costo_por_caja'] = redondear(costo_por_caja)
                    lote_data['costo_por_mango'] = redondear(costo_por_mango)
                    lote_data['precio_recomendado_caja'] = redondear(precio_recomendado_caja)
                    lote_data['precio_recomendado_mango'] = redondear(precio_recomendado_mango)
                    lote_data['precio_recomendado_kg'] = redondear(precio_recomendado_kg)
                    lote_data['costo_kg'] = redondear(costo_kg)
                    lote_data['margen'] = redondear(margen_deseado * 100)  # 30%
                    lote_data['ganancia_por_caja'] = redondear(ganancia_por_caja)
                    lote_data['ganancia_total'] = redondear(ganancia_total)
                    
                    # Resumen para mangos
                    lote_data['resumen_producto'] = f"Calibre {calibre_num} | ${redondear(costo_por_caja):,.0f}/caja | ${redondear(precio_recomendado_caja):,.0f}/caja rec."
                except Exception as e:
                    lote_data['resumen_producto'] = f"Calibre {lote.calibre} | Información no disponible"
            
            # Información específica para plátanos
            elif tipo_producto == 'platano' and es_admin_o_supervisor:
                try:
                    # El costo por caja es el costo_actualizado (ya viene por caja)
                    costo_por_caja = float(lote.costo_actualizado() or 0)
                    
                    # Calcular precio recomendado basado en costo y margen deseado
                    margen_deseado = 0.25  # 25% de margen
                    precio_recomendado_caja = costo_por_caja / (1 - margen_deseado) if margen_deseado < 1 else 0
                    
                    # Calcular precio por kg (solo para referencia)
                    peso_por_caja = float(lote.peso_neto) / float(lote.cantidad_cajas) if lote.cantidad_cajas and lote.cantidad_cajas > 0 else 0
                    precio_recomendado_kg = precio_recomendado_caja / peso_por_caja if peso_por_caja > 0 else 0
                    costo_kg = costo_por_caja / peso_por_caja if peso_por_caja > 0 else 0
                    
                    # Calcular ganancia y margen
                    ganancia_por_caja = precio_recomendado_caja - costo_por_caja
                    ganancia_total = ganancia_por_caja * float(lote.cantidad_cajas or 0)
                    
                    # Agregar información específica de plátanos
                    lote_data['costo_por_caja'] = redondear(costo_por_caja)
                    lote_data['precio_recomendado_caja'] = redondear(precio_recomendado_caja)
                    lote_data['precio_recomendado_kg'] = redondear(precio_recomendado_kg)
                    lote_data['costo_kg'] = redondear(costo_kg)
                    lote_data['margen'] = redondear(margen_deseado * 100)  # 25%
                    lote_data['ganancia_por_caja'] = redondear(ganancia_por_caja)
                    lote_data['ganancia_total'] = redondear(ganancia_total)
                    
                    # Resumen para plátanos
                    lote_data['resumen_producto'] = f"${redondear(costo_por_caja):,.0f}/caja | ${redondear(precio_recomendado_caja):,.0f}/caja rec. | {redondear(peso_por_caja)}kg/caja"
                except Exception as e:
                    lote_data['resumen_producto'] = f"Información no disponible"
            
            # Añadir el lote al resultado
            resultados.append(lote_data)
        
        # Generar resumen por producto
        productos_dict = {}
        for lote in resultados:
            producto_id = lote.get('producto_id')
            
            # Si el producto no está en el diccionario, inicializarlo
            if producto_id not in productos_dict:
                productos_dict[producto_id] = {
                    'producto_id': producto_id,
                    'producto_nombre': lote.get('producto_nombre'),
                    'total_lotes': 0,
                    'peso_total': 0,
                    'peso_disponible': 0,
                    'peso_reservado': 0,
                    'valor_total': 0,
                    'es_palta': 'es_palta' in lote and lote['es_palta'],
                    'tipo_producto': lote.get('tipo_producto', 'otro'),
                    'distribucion_maduracion': {
                        'verde': {'cantidad': 0, 'peso': 0},
                        'pre-maduro': {'cantidad': 0, 'peso': 0},
                        'maduro': {'cantidad': 0, 'peso': 0},
                        'sobremaduro': {'cantidad': 0, 'peso': 0}
                    } if 'es_palta' in lote and lote['es_palta'] else None,
                    'perdida_estimada': {'kg': 0, 'porcentaje': 0, 'valor': 0} if 'es_palta' in lote and lote['es_palta'] else None,
                    'precio_promedio': 0,
                    'margen_promedio': 0,
                    'ganancia_promedio_kg': 0,
                    'ingreso_estimado': 0,
                    'ganancia_estimada': 0,
                    'lotes_urgentes': 0,
                    'peso_vendible': 0 if 'es_palta' in lote and lote['es_palta'] else None,
                    'lotes_con_precio': 0
                }
            
            # Actualizar contadores básicos
            productos_dict[producto_id]['total_lotes'] += 1
            productos_dict[producto_id]['peso_total'] += float(lote.get('peso_neto', 0) or 0)
            productos_dict[producto_id]['peso_disponible'] += float(lote.get('peso_disponible', 0) or 0)
            productos_dict[producto_id]['peso_reservado'] += float(lote.get('peso_reservado', 0) or 0)
            productos_dict[producto_id]['valor_total'] += float(lote.get('valor_total', 0) or 0)
            
            # Actualizar datos específicos para paltas
            if 'es_palta' in lote and lote['es_palta'] and 'estado_maduracion' in lote:
                estado = lote['estado_maduracion']
                peso_neto = float(lote.get('peso_neto', 0) or 0)
                productos_dict[producto_id]['distribucion_maduracion'][estado]['cantidad'] += 1
                productos_dict[producto_id]['distribucion_maduracion'][estado]['peso'] += peso_neto
                
                # Actualizar pérdida estimada
                productos_dict[producto_id]['perdida_estimada']['kg'] += float(lote.get('perdida_estimada', 0) or 0)
                productos_dict[producto_id]['perdida_estimada']['valor'] += float(lote.get('valor_perdida', 0) or 0)
                productos_dict[producto_id]['peso_vendible'] += float(lote.get('peso_vendible', 0) or 0)
                
                # Contar lotes urgentes
                if lote.get('urgencia_venta') in ['alta', 'critica']:
                    productos_dict[producto_id]['lotes_urgentes'] += 1
            
            # Acumular datos para promedios
            if lote.get('precio_recomendado_kg', 0):
                productos_dict[producto_id]['precio_promedio'] += float(lote.get('precio_recomendado_kg', 0) or 0)
                productos_dict[producto_id]['margen_promedio'] += float(lote.get('margen', 0) or 0)
                productos_dict[producto_id]['ganancia_promedio_kg'] += float(lote.get('ganancia_kg', 0) or 0)
                productos_dict[producto_id]['ingreso_estimado'] += float(lote.get('ingreso_estimado', 0) or 0)
                productos_dict[producto_id]['ganancia_estimada'] += float(lote.get('ganancia_total', 0) or 0)
                productos_dict[producto_id]['lotes_con_precio'] += 1
        
        # Calcular promedios
        resumen_productos = []
        for producto_id, producto_data in productos_dict.items():
            # Calcular porcentaje de pérdida promedio para paltas
            if producto_data['es_palta'] and producto_data['peso_total'] > 0:
                producto_data['perdida_estimada']['porcentaje'] = redondear(
                    (float(producto_data['perdida_estimada']['kg']) / float(producto_data['peso_total'])) * 100
                )
            
            # Calcular promedios si hay lotes con precio
            lotes_con_precio = producto_data['lotes_con_precio']
            if lotes_con_precio > 0:
                producto_data['precio_promedio'] = redondear(producto_data['precio_promedio'] / lotes_con_precio)
                producto_data['margen_promedio'] = redondear(producto_data['margen_promedio'] / lotes_con_precio)
                producto_data['ganancia_promedio_kg'] = redondear(producto_data['ganancia_promedio_kg'] / lotes_con_precio)
            
            # Redondear valores numéricos
            producto_data['peso_total'] = redondear(producto_data['peso_total'])
            producto_data['peso_disponible'] = redondear(producto_data['peso_disponible'])
            producto_data['peso_reservado'] = redondear(producto_data['peso_reservado'])
            producto_data['valor_total'] = redondear(producto_data['valor_total'])
            if producto_data['es_palta']:
                producto_data['perdida_estimada']['kg'] = redondear(producto_data['perdida_estimada']['kg'])
                producto_data['perdida_estimada']['valor'] = redondear(producto_data['perdida_estimada']['valor'])
                producto_data['peso_vendible'] = redondear(producto_data['peso_vendible'])
                
                # Redondear pesos en distribución de maduración
                for estado in producto_data['distribucion_maduracion']:
                    producto_data['distribucion_maduracion'][estado]['peso'] = redondear(
                        producto_data['distribucion_maduracion'][estado]['peso']
                    )
            
            # Eliminar campo auxiliar
            del producto_data['lotes_con_precio']
            
            # Añadir al resumen
            resumen_productos.append(producto_data)
        
        # Generar resumen general para paltas si hay paltas en el inventario
        resumen_general_paltas = None
        recomendaciones_paltas = []
        resumen_paltas_por_calibre = []
        
        # Verificar si hay paltas en el inventario
        lotes_paltas = [lote for lote in resultados if lote.get('es_palta', False)]
        if lotes_paltas:
            # Calcular totales para paltas
            total_kg_paltas = sum(float(lote.get('peso_neto', 0) or 0) for lote in lotes_paltas)
            total_disponible_paltas = sum(float(lote.get('peso_disponible', 0) or 0) for lote in lotes_paltas)
            total_reservado_paltas = sum(float(lote.get('peso_reservado', 0) or 0) for lote in lotes_paltas)
            total_perdida_kg = sum(float(lote.get('perdida_estimada', 0) or 0) for lote in lotes_paltas)
            total_perdida_valor = sum(float(lote.get('valor_perdida', 0) or 0) for lote in lotes_paltas)
            total_vendible = sum(float(lote.get('peso_vendible', 0) or 0) for lote in lotes_paltas)
            
            # Calcular porcentaje de pérdida promedio
            porcentaje_perdida_promedio = (float(total_perdida_kg) / float(total_kg_paltas) * 100) if total_kg_paltas > 0 else 0
            
            # Contar lotes por estado de maduración
            distribucion_maduracion = {
                'verde': {'cantidad': 0, 'peso': 0},
                'pre-maduro': {'cantidad': 0, 'peso': 0},
                'maduro': {'cantidad': 0, 'peso': 0},
                'sobremaduro': {'cantidad': 0, 'peso': 0}
            }
            
            for lote in lotes_paltas:
                if 'estado_maduracion' in lote:
                    estado = lote['estado_maduracion']
                    distribucion_maduracion[estado]['cantidad'] += 1
                    distribucion_maduracion[estado]['peso'] += float(lote.get('peso_neto', 0) or 0)
            
            # Crear resumen general de paltas
            resumen_general_paltas = {
                'total_kg': redondear(total_kg_paltas),
                'total_disponible': redondear(total_disponible_paltas),
                'total_reservado': redondear(total_reservado_paltas),
                'total_vendible': redondear(total_vendible),
                'perdida_estimada': {
                    'kg': redondear(total_perdida_kg),
                    'porcentaje': redondear(porcentaje_perdida_promedio),
                    'valor': redondear(total_perdida_valor)
                },
                'distribucion_maduracion': distribucion_maduracion
            }
            
            # Redondear pesos en distribución de maduración
            for estado in distribucion_maduracion:
                distribucion_maduracion[estado]['peso'] = redondear(distribucion_maduracion[estado]['peso'])
            
            # Generar recomendaciones para paltas
            if distribucion_maduracion['sobremaduro']['cantidad'] > 0:
                recomendaciones_paltas.append({
                    'tipo': 'urgente',
                    'mensaje': f"Priorizar venta de {distribucion_maduracion['sobremaduro']['cantidad']} lotes sobremaduros ({redondear(distribucion_maduracion['sobremaduro']['peso'])}kg)",
                    'accion': 'liquidar'
                })
            if distribucion_maduracion['maduro']['cantidad'] > 0:
                recomendaciones_paltas.append({
                    'tipo': 'importante',
                    'mensaje': f"Vender {distribucion_maduracion['maduro']['cantidad']} lotes maduros ({redondear(distribucion_maduracion['maduro']['peso'])}kg) en los próximos 3 días",
                    'accion': 'vender'
                })
            
            # Generar resumen por calibre
            calibres = {}
            for lote in lotes_paltas:
                calibre = lote.get('calibre', 'Sin calibre')
                if calibre not in calibres:
                    calibres[calibre] = {
                        'calibre': calibre,
                        'cantidad_lotes': 0,
                        'peso_total': 0,
                        'peso_disponible': 0,
                        'distribucion_maduracion': {
                            'verde': 0,
                            'pre-maduro': 0,
                            'maduro': 0,
                            'sobremaduro': 0
                        },
                        'precio_promedio': 0,
                        'lotes_con_precio': 0
                    }
                calibres[calibre]['cantidad_lotes'] += 1
                calibres[calibre]['peso_total'] += float(lote.get('peso_neto', 0) or 0)
                calibres[calibre]['peso_disponible'] += float(lote.get('peso_disponible', 0) or 0)
                if 'estado_maduracion' in lote:
                    calibres[calibre]['distribucion_maduracion'][lote['estado_maduracion']] += float(lote.get('peso_neto', 0) or 0)
                if lote.get('precio_recomendado_kg', 0):
                    calibres[calibre]['precio_promedio'] += float(lote.get('precio_recomendado_kg', 0) or 0)
                    calibres[calibre]['lotes_con_precio'] += 1
            
            # Calcular promedios y redondear valores
            for calibre, data in calibres.items():
                if data['lotes_con_precio'] > 0:
                    data['precio_promedio'] = redondear(data['precio_promedio'] / data['lotes_con_precio'])
                
                data['peso_total'] = redondear(data['peso_total'])
                data['peso_disponible'] = redondear(data['peso_disponible'])
                
                for estado in data['distribucion_maduracion']:
                    data['distribucion_maduracion'][estado] = redondear(data['distribucion_maduracion'][estado])
                
                del data['lotes_con_precio']
                resumen_paltas_por_calibre.append(data)
        
        # Preparar la respuesta final y optimizar datos
        # Filtrar campos redundantes y asegurar valores financieros correctos
        for lote in resultados:
            # Asegurar que los campos financieros tengan valores razonables
            if lote.get('precio_recomendado_kg', 0) == 0:
                # Si no se calculó precio recomendado, usar un margen mínimo del 25%
                costo_kg = lote.get('costo_real_kg', 0)
                if costo_kg == 0 and lote.get('costo_actual', 0) > 0 and lote.get('peso_neto', 0) > 0:
                    costo_kg = float(lote.get('costo_actual', 0)) / float(lote.get('peso_neto', 0))
                lote['precio_recomendado_kg'] = round(costo_kg * 1.25, 2)  # Margen mínimo del 25%
                
                # Recalcular valores derivados
                lote['ganancia_kg'] = round(lote['precio_recomendado_kg'] - costo_kg, 2)
                lote['margen'] = round((lote['ganancia_kg'] / costo_kg * 100) if costo_kg > 0 else 25, 2)
                lote['ingreso_estimado'] = round(lote['precio_recomendado_kg'] * lote.get('peso_vendible', 0), 2)
                lote['ganancia_total'] = round(lote['ganancia_kg'] * lote.get('peso_vendible', 0), 2)
                
            # Actualizar el resumen del producto con los nuevos valores
            lote['resumen_producto'] = f"{lote.get('producto_nombre', '')} {lote.get('calibre', 'S/C')} | ${lote.get('costo_real_kg', 0):,.0f}/kg | ${lote.get('precio_recomendado_kg', 0):,.0f}/kg rec. | {lote.get('estado_maduracion', '').capitalize()}"
            
            # Extraer la proyección de maduración a nivel de producto para evitar repetición
            # Solo guardamos la recomendación en cada lote, no toda la proyección
            if 'proyeccion_maduracion' in lote:
                recomendacion = lote.get('recomendacion', {})
                lote['recomendacion'] = recomendacion
                lote.pop('proyeccion_maduracion', None)
            
            # Eliminar campos redundantes o innecesarios
            campos_a_eliminar = [
                'created_at', 'updated_at', 'fecha_maduracion', 'porcentaje_perdida_estimado',
                'mostrar_detalle', 'business', 'tiene_detalle_maduracion',
                'es_palta', 'es_mango', 'es_platano', 'box_type', 'pallet_type', 'producto',
                'valor_total', 'escenarios_precio'
            ]
            for campo in campos_a_eliminar:
                if campo in lote:
                    lote.pop(campo, None)
            
            # Agregar costo total del pallet y ganancia total
            costo_real_kg = float(lote.get('costo_real_kg', 0) or 0)
            peso_neto = float(lote.get('peso_neto', 0) or 0)
            precio_recomendado = float(lote.get('precio_recomendado_kg', 0) or 0)
            lote['costo_total_pallet'] = round(costo_real_kg * peso_neto, 2)
            lote['ganancia_total'] = round((precio_recomendado - costo_real_kg) * peso_neto, 2)
        
        # Recalcular los resúmenes por producto con los valores actualizados
        for producto in resumen_productos:
            lotes_producto = [l for l in resultados if l.get('producto_nombre') == producto.get('producto_nombre')]
            if lotes_producto:
                # Calcular promedios de precios y márgenes
                precio_total = sum(l.get('precio_recomendado_kg', 0) for l in lotes_producto)
                margen_total = sum(l.get('margen', 0) for l in lotes_producto)
                ganancia_total = sum(l.get('ganancia_kg', 0) for l in lotes_producto)
                ingreso_total = sum(l.get('ingreso_estimado', 0) for l in lotes_producto)
                ganancia_estimada = sum(l.get('ganancia_total', 0) for l in lotes_producto)
                
                producto['precio_promedio'] = round(precio_total / len(lotes_producto), 2)
                producto['margen_promedio'] = round(margen_total / len(lotes_producto), 2)
                producto['ganancia_promedio_kg'] = round(ganancia_total / len(lotes_producto), 2)
                producto['ingreso_estimado'] = round(ingreso_total, 2)
                producto['ganancia_estimada'] = round(ganancia_estimada, 2)
        
        # Extraer proyección de maduración para paltas (una sola vez para todos los lotes)
        proyeccion_maduracion_paltas = None
        for lote in resultados:
            if lote.get('tipo_producto') == 'palta' and 'proyeccion_maduracion' in lote:
                proyeccion_maduracion_paltas = lote.get('proyeccion_maduracion')
                break
                
        # Simplificar la estructura de la respuesta
        response_data = {
            'periodo': {
                'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': fecha_fin.strftime('%Y-%m-%d')
            },
            'filtros_aplicados': {
                'tipo_producto': tipo_producto if tipo_producto else 'todos',
                'producto_id': producto_id if producto_id else None,
                'nombre_producto': nombre_producto if nombre_producto else None,
                'calibre': calibre if calibre else None
            },
            'resumen': {
                'total_productos': len(resumen_productos),
                'total_lotes': len(resultados),
                'productos': resumen_productos
            },
            'lotes': resultados
        }
        
        # Añadir proyección de maduración a nivel global si hay paltas
        if proyeccion_maduracion_paltas:
            response_data['proyeccion_maduracion_paltas'] = proyeccion_maduracion_paltas
        
        # Incluir información específica según el tipo de producto y producto_id
        if producto_id or nombre_producto:
            # Si se filtró por un producto específico (por ID o nombre), proporcionar datos detallados
            producto_especifico = None
            for producto in resumen_productos:
                # Buscar por ID si se especificó
                if producto_id and str(producto.get('producto_id')) == str(producto_id):
                    producto_especifico = producto
                    break
                # Buscar por nombre si se especificó
                elif nombre_producto and nombre_producto.lower() in producto.get('producto_nombre', '').lower():
                    producto_especifico = producto
                    break
            
            if producto_especifico:
                # Determinar el tipo de producto (palta, mango, plátano u otro)
                es_palta = producto_especifico.get('es_palta', False)
                es_mango = 'mango' in producto_especifico.get('producto_nombre', '').lower()
                es_platano = 'platano' in producto_especifico.get('producto_nombre', '').lower() or 'plátano' in producto_especifico.get('producto_nombre', '').lower()
                
                # Filtrar lotes solo de este producto
                if producto_id:
                    lotes_producto = [lote for lote in resultados if str(lote.get('producto_id')) == str(producto_id)]
                else:
                    # Si filtramos por nombre, usamos el nombre para filtrar los lotes
                    lotes_producto = [lote for lote in resultados if nombre_producto.lower() in lote.get('producto_nombre', '').lower()]
                
                # Calcular datos específicos para este producto según su tipo
                if es_palta:
                    # Para paltas, incluir datos de maduración y precios recomendados
                    total_kilos_vendibles = sum(float(lote.get('peso_vendible', 0) or 0) for lote in lotes_producto)
                    total_ingreso_estimado = sum(float(lote.get('ingreso_estimado', 0) or 0) for lote in lotes_producto)
                    
                    # Distribución de maduración para este producto específico
                    distribucion_maduracion = {
                        'verde': {'cantidad': 0, 'peso': 0},
                        'pre-maduro': {'cantidad': 0, 'peso': 0},
                        'maduro': {'cantidad': 0, 'peso': 0},
                        'sobremaduro': {'cantidad': 0, 'peso': 0}
                    }
                    
                    for lote in lotes_producto:
                        if 'estado_maduracion' in lote:
                            estado = lote['estado_maduracion']
                            distribucion_maduracion[estado]['cantidad'] += 1
                            distribucion_maduracion[estado]['peso'] += float(lote.get('peso_neto', 0) or 0)
                    
                    # Redondear pesos en distribución de maduración
                    for estado in distribucion_maduracion:
                        distribucion_maduracion[estado]['peso'] = redondear(distribucion_maduracion[estado]['peso'])
                    
                    # En lugar de crear un objeto detalle_producto separado, enriquecemos el producto en resumen.productos
                    for producto in response_data['resumen']['productos']:
                        if producto.get('producto_nombre') == producto_especifico.get('producto_nombre'):
                            # Añadir información adicional útil sin duplicar
                            producto['calibres_disponibles'] = list(set(lote.get('calibre', '') for lote in lotes_producto if lote.get('calibre')))
                            # No duplicamos la distribución de maduración porque ya está en el producto
                            break
                elif es_mango:
                    # Para mangos, enfocarse en cajas, calibres y datos específicos de mangos
                    total_cajas = sum(lote.get('cantidad_cajas', 0) for lote in lotes_producto)
                    total_valor = sum(float(lote.get('valor_total', 0) or 0) for lote in lotes_producto)
                    
                    # Calcular datos específicos para mangos
                    mangos_por_caja = 0
                    peso_por_mango = 0
                    costo_por_caja = 0
                    precio_recomendado_caja = 0
                    lotes_con_datos = 0
                    
                    for lote in lotes_producto:
                        if lote.get('cantidad_cajas') and lote.get('calibre'):
                            try:
                                # El calibre en mangos suele indicar la cantidad por caja
                                calibre_num = int(lote.get('calibre', '0'))
                                if calibre_num > 0:
                                    mangos_por_caja += calibre_num
                                    if lote.get('peso_neto') and calibre_num > 0:
                                        peso_por_mango += float(lote.get('peso_neto', 0) or 0) / calibre_num
                                    if lote.get('costo_por_caja'):
                                        costo_por_caja += float(lote.get('costo_por_caja', 0) or 0)
                                    if lote.get('precio_recomendado_caja'):
                                        precio_recomendado_caja += float(lote.get('precio_recomendado_caja', 0) or 0)
                                    lotes_con_datos += 1
                            except (ValueError, TypeError):
                                pass
                    
                    # Calcular promedios
                    if lotes_con_datos > 0:
                        mangos_por_caja = redondear(mangos_por_caja / lotes_con_datos)
                        peso_por_mango = redondear(peso_por_mango / lotes_con_datos)
                        costo_por_caja = redondear(costo_por_caja / lotes_con_datos)
                        precio_recomendado_caja = redondear(precio_recomendado_caja / lotes_con_datos)
                    
                    response_data['detalle_producto'] = {
                        'id': producto_especifico.get('producto_id'),
                        'nombre': producto_especifico.get('producto_nombre', ''),
                        'tipo': 'mango',
                        'total_lotes': len(lotes_producto),
                        'total_cajas': total_cajas,
                        'peso_total': redondear(producto_especifico.get('peso_total', 0)),
                        'valor_total': redondear(total_valor),
                        'mangos_por_caja': mangos_por_caja,
                        'peso_por_mango': peso_por_mango,
                        'costo_por_caja': costo_por_caja,
                        'precio_recomendado_caja': precio_recomendado_caja,
                        'calibres_disponibles': list(set(lote.get('calibre', '') for lote in lotes_producto if lote.get('calibre')))
                    }
                elif es_platano:
                    # Para plátanos, enfocarse en cajas y datos específicos
                    total_cajas = sum(lote.get('cantidad_cajas', 0) for lote in lotes_producto)
                    total_valor = sum(float(lote.get('valor_total', 0) or 0) for lote in lotes_producto)
                    
                    # Calcular datos específicos para plátanos
                    peso_por_caja = 0
                    costo_por_caja = 0
                    precio_recomendado_caja = 0
                    lotes_con_datos = 0
                    
                    for lote in lotes_producto:
                        if lote.get('cantidad_cajas'):
                            if lote.get('peso_neto') and lote.get('cantidad_cajas'):
                                peso_por_caja += float(lote.get('peso_neto', 0) or 0) / float(lote.get('cantidad_cajas'))
                            if lote.get('costo_por_caja'):
                                costo_por_caja += float(lote.get('costo_por_caja', 0) or 0)
                            if lote.get('precio_recomendado_caja'):
                                precio_recomendado_caja += float(lote.get('precio_recomendado_caja', 0) or 0)
                            lotes_con_datos += 1
                    
                    # Calcular promedios
                    if lotes_con_datos > 0:
                        peso_por_caja = redondear(peso_por_caja / lotes_con_datos)
                        costo_por_caja = redondear(costo_por_caja / lotes_con_datos)
                        precio_recomendado_caja = redondear(precio_recomendado_caja / lotes_con_datos)
                    
                    response_data['detalle_producto'] = {
                        'id': producto_especifico.get('producto_id'),
                        'nombre': producto_especifico.get('producto_nombre', ''),
                        'tipo': 'platano',
                        'total_lotes': len(lotes_producto),
                        'total_cajas': total_cajas,
                        'peso_total': redondear(producto_especifico.get('peso_total', 0)),
                        'valor_total': redondear(total_valor),
                        'peso_por_caja': peso_por_caja,
                        'costo_por_caja': costo_por_caja,
                        'precio_recomendado_caja': precio_recomendado_caja,
                        'calibres_disponibles': list(set(lote.get('calibre', '') for lote in lotes_producto if lote.get('calibre')))
                    }
                else:
                    # Para otros productos, enfocarse en cajas y valor
                    total_cajas = sum(lote.get('cantidad_cajas', 0) for lote in lotes_producto)
                    total_valor = sum(float(lote.get('valor_total', 0) or 0) for lote in lotes_producto)
                    
                    response_data['detalle_producto'] = {
                        'id': producto_especifico.get('producto_id'),
                        'nombre': producto_especifico.get('producto_nombre', ''),
                        'tipo': 'otro',
                        'total_lotes': len(lotes_producto),
                        'total_cajas': total_cajas,
                        'peso_total': redondear(producto_especifico.get('peso_total', 0)),
                        'valor_total': redondear(total_valor),
                        'calibres_disponibles': list(set(lote.get('calibre', '') for lote in lotes_producto if lote.get('calibre')))
                    }
        
        # Información general según tipo de producto (si no se filtró por producto específico o además del filtro)
        if tipo_producto == 'paltas' or not tipo_producto:
            response_data['resumen_general_paltas'] = resumen_general_paltas
            response_data['recomendaciones_paltas'] = recomendaciones_paltas
            response_data['resumen_paltas_por_calibre'] = resumen_paltas_por_calibre
            
            # Calcular totales específicos para paltas
            total_kilos_vendibles = sum(float(lote.get('peso_vendible', 0) or 0) for lote in resultados if 'es_palta' in lote and lote['es_palta'])
            total_ingreso_estimado = sum(float(lote.get('ingreso_estimado', 0) or 0) for lote in resultados if 'es_palta' in lote and lote['es_palta'])
            
            response_data['totales_paltas'] = {
                'total_kilos_vendibles': redondear(total_kilos_vendibles),
                'total_ingreso_estimado': redondear(total_ingreso_estimado)
            }
            
        elif tipo_producto == 'otros':
            # Para otros productos, calcular totales por cajas
            total_cajas = sum(lote.get('cantidad_cajas', 0) for lote in resultados)
            total_valor = sum(float(lote.get('valor_inventario', 0) or 0) for lote in resultados)
            
            response_data['totales_otros'] = {
                'total_cajas': total_cajas,
                'total_valor': redondear(total_valor)
            }
            
            # Eliminar información específica de paltas que no es relevante
            if 'resumen_general_paltas' in response_data:
                del response_data['resumen_general_paltas']
            if 'recomendaciones_paltas' in response_data:
                del response_data['recomendaciones_paltas']
            if 'resumen_paltas_por_calibre' in response_data:
                del response_data['resumen_paltas_por_calibre']
        
        return Response(response_data)

class SalesReportView(APIView):
    permission_classes = [IsAuthenticated, IsSameBusiness]
    def get(self, request):
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        # Parámetros de filtrado
        
        start_date_param = request.query_params.get('start_date', None)
        end_date_param = request.query_params.get('end_date', None)
        vendedor_id = request.query_params.get('vendedor_id', None)
        cliente_id = request.query_params.get('cliente_id', None)
        producto_id = request.query_params.get('producto_id', None)
        
        # Si no se proporcionan fechas, usar últimos 30 días
        if not start_date_param:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = parse_date(start_date_param)
            end_date = parse_date(end_date_param) if end_date_param else datetime.now().date()
            if end_date:
                end_date = datetime.combine(end_date, datetime.max.time())
        
        # Usar modelos y funciones importadas en la cabecera
        
        # Queryset base - todas las ventas del negocio en el período
        queryset = Sale.objects.filter(
            business=perfil.business,
            created_at__range=[start_date, end_date]
        ).select_related('vendedor', 'cliente', 'lote__producto')
        
        # Aplicar filtros adicionales
        if vendedor_id:
            queryset = queryset.filter(vendedor_id=vendedor_id)
        
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)
            
        if producto_id:
            queryset = queryset.filter(lote__producto_id=producto_id)
        
        # Preparar resultados
        ventas_detalladas = []
        for venta in queryset:
            ventas_detalladas.append({
                'id': venta.id,
                'fecha': venta.created_at,
                'vendedor_id': venta.vendedor_id,
                'vendedor_nombre': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip() or venta.vendedor.username,
                'cliente_id': venta.cliente_id,
                'cliente_nombre': venta.cliente.nombre if venta.cliente else "Cliente ocasional",
                'producto_id': venta.lote.producto_id if venta.lote else None,
                'producto_nombre': venta.lote.producto.nombre if venta.lote and venta.lote.producto else "Desconocido",
                'calibre': venta.lote.calibre if venta.lote else None,
                'cantidad_kg': venta.peso_vendido,
                'precio_por_kg': venta.precio_kg,
                'total': venta.total
            })
        
        # Agregados por día
        ventas_por_dia = queryset.annotate(
            fecha_dia=TruncDate('created_at')
        ).values('fecha_dia').annotate(
            total_ventas=Count('id'),
            total_kg=Sum('items__peso_vendido'),
            total_ingresos=Sum('items__peso_vendido' * 'items__precio_kg', output_field=DecimalField())
        ).order_by('fecha_dia')
        
        # Agregados por vendedor
        ventas_por_vendedor = queryset.values(
            'vendedor_id',
            vendedor_nombre=F('vendedor__first_name')
        ).annotate(
            total_ventas=Count('id'),
            total_kg=Sum('items__peso_vendido'),
            total_ingresos=Sum('items__peso_vendido' * 'items__precio_kg', output_field=DecimalField())
        ).order_by('-total_ingresos')
        
        # Modificar para agregar nombre completo
        for item in ventas_por_vendedor:
            vendedor = queryset.filter(vendedor_id=item['vendedor_id']).first().vendedor
            item['vendedor_nombre'] = f"{vendedor.first_name} {vendedor.last_name}".strip() or vendedor.username
        
        # Agregados por producto
        ventas_por_producto = queryset.values(
            'lote__producto_id',
            producto_nombre=F('lote__producto__nombre')
        ).annotate(
            total_ventas=Count('id'),
            total_kg=Sum('items__peso_vendido'),
            total_ingresos=Sum('items__peso_vendido' * 'items__precio_kg', output_field=DecimalField())
        ).order_by('-total_kg')
        
        # Calcular totales
        total_ventas = queryset.count()
        total_kg = queryset.aggregate(total=Sum('peso_vendido'))['total'] or 0
        total_ingresos = queryset.aggregate(
            total=Sum('total', output_field=DecimalField())
        )['total'] or 0
        
        return Response({
            'periodo': {
                'fecha_inicio': start_date,
                'fecha_fin': end_date
            },
            'totales': {
                'total_ventas': total_ventas,
                'total_kg': total_kg,
                'total_ingresos': total_ingresos
            },
            'ventas_por_dia': list(ventas_por_dia),
            'ventas_por_vendedor': list(ventas_por_vendedor),
            'ventas_por_producto': list(ventas_por_producto),
            'ventas_detalladas': ventas_detalladas
        })
        
        
        
    
class ShiftReportView(APIView):
    permission_classes = [IsAuthenticated, IsSameBusiness]
    def get(self, request):
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado.'}, status=404)
        
        # Parámetros de filtrado
        start_date_param = request.query_params.get('start_date', None)
        end_date_param = request.query_params.get('end_date', None)
        usuario_id = request.query_params.get('usuario_id', None)
        estado = request.query_params.get('estado', None)
        
        # Si no se proporcionan fechas, usar últimos 30 días
        if not start_date_param:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = parse_date(start_date_param)
            end_date = parse_date(end_date_param) if end_date_param else datetime.now().date()
            if end_date:
                end_date = datetime.combine(end_date, datetime.max.time())
        
        # Usar modelos y funciones importadas en la cabecera
        
        # Queryset base - todos los turnos del negocio en el período
        queryset = Shift.objects.filter(
            business=perfil.business,
            fecha_apertura__range=[start_date, end_date]
        ).select_related('usuario_abre', 'usuario_cierra')
        
        # Aplicar filtros adicionales
        if usuario_id:
            queryset = queryset.filter(
                Q(usuario_abre_id=usuario_id) | Q(usuario_cierra_id=usuario_id)
            )
        
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Procesar resultados
        turnos_data = []
        for turno in queryset:
            # Obtener ventas realizadas durante este turno
            ventas_condicion = Q(
                business=perfil.business,
                created_at__range=[turno.fecha_apertura, turno.fecha_cierre or datetime.now()]
            )
            
            # Si es turno cerrado, calcular hasta fecha de cierre
            if turno.estado == "cerrado" and turno.fecha_cierre:
                ventas_condicion = Q(
                    business=perfil.business,
                    created_at__range=[turno.fecha_apertura, turno.fecha_cierre]
                )
            
            # Si el turno está abierto, calcular hasta ahora
            ventas = Sale.objects.filter(ventas_condicion)
            
            # Calcular totales de ventas
            total_ventas = ventas.count()
            total_kg = ventas.aggregate(total=Sum('items__peso_vendido'))['total'] or 0
            total_ingresos = ventas.aggregate(
                total=Sum('items__peso_vendido' * 'items__precio_kg', output_field=DecimalField())
            )['total'] or 0
            
            # Calcular duración en minutos
            duracion_minutos = 0
            if turno.fecha_apertura and turno.fecha_cierre:
                delta = turno.fecha_cierre - turno.fecha_apertura
                duracion_minutos = int(delta.total_seconds() / 60)
            elif turno.fecha_apertura:
                delta = datetime.now() - turno.fecha_apertura.replace(tzinfo=None)
                duracion_minutos = int(delta.total_seconds() / 60)
            
            # Crear objeto de turno con datos de ventas
            turnos_data.append({
                'id': turno.id,
                'usuario_abre_id': turno.usuario_abre_id,
                'usuario_abre_nombre': f"{turno.usuario_abre.first_name} {turno.usuario_abre.last_name}".strip() or turno.usuario_abre.username,
                'usuario_cierra_id': turno.usuario_cierra_id,
                'usuario_cierra_nombre': f"{turno.usuario_cierra.first_name} {turno.usuario_cierra.last_name}".strip() if turno.usuario_cierra else None,
                'fecha_apertura': turno.fecha_apertura,
                'fecha_cierre': turno.fecha_cierre,
                'duracion_minutos': duracion_minutos,
                'estado': turno.estado,
                'motivo_diferencia': turno.motivo_diferencia,
                'ventas': {
                    'total_ventas': total_ventas,
                    'total_kg': total_kg,
                    'total_ingresos': total_ingresos
                }
            })
        
        # Calcular agregados por usuario
        usuarios_data = {}
        for turno in turnos_data:
            usuario_id = turno['usuario_abre_id']
            if usuario_id not in usuarios_data:
                usuarios_data[usuario_id] = {
                    'usuario_nombre': turno['usuario_abre_nombre'],
                    'total_turnos': 0,
                    'total_duracion_minutos': 0,
                    'total_ventas': 0,
                    'total_kg': 0,
                    'total_ingresos': 0
                }
            
            usuarios_data[usuario_id]['total_turnos'] += 1
            usuarios_data[usuario_id]['total_duracion_minutos'] += turno['duracion_minutos']
            usuarios_data[usuario_id]['total_ventas'] += turno['ventas']['total_ventas']
            usuarios_data[usuario_id]['total_kg'] += turno['ventas']['total_kg']
            usuarios_data[usuario_id]['total_ingresos'] += turno['ventas']['total_ingresos']
        
        # Convertir a lista
        usuarios_lista = []
        for usuario_id, data in usuarios_data.items():
            usuarios_lista.append({
                'usuario_id': usuario_id,
                'usuario_nombre': data['usuario_nombre'],
                'total_turnos': data['total_turnos'],
                'total_duracion_minutos': data['total_duracion_minutos'],
                'total_ventas': data['total_ventas'],
                'total_kg': data['total_kg'],
                'total_ingresos': data['total_ingresos']
            })
            
        return Response({
            'periodo': {
                'fecha_inicio': start_date,
                'fecha_fin': end_date
            },
            'turnos': turnos_data,
            'agregados_por_usuario': usuarios_lista,
            'total_turnos': len(turnos_data)
        })
