from django.db.models import Q, F, Sum, Count, Case, When, Value, CharField, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
import json
from decimal import Decimal
from inventory.models import FruitLot, MadurationHistory

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def generar_reporte_maduracion_paltas(business_id=None, lote_id=None, producto_id=None, 
                               pallet_id=None, calibre=None, estado_maduracion=None):
    """
    Genera un reporte detallado sobre la maduración de paltas para un negocio específico,
    con opciones de filtrado por lote, producto, pallet, calibre o estado de maduración.
    
    Parámetros:
    - business_id: ID del negocio (opcional)
    - lote_id: ID específico del lote (opcional)
    - producto_id: ID del producto (opcional)
    - pallet_id: Código QR o identificador del pallet (opcional)
    - calibre: Calibre específico (opcional)
    - estado_maduracion: Estado de maduración específico (opcional)
    
    Ejemplos de uso desde el shell de Django:
    
    from inventory.utils.maduracion_report import generar_reporte_maduracion_paltas
    
    # Para un negocio específico
    generar_reporte_maduracion_paltas(business_id=1)
    
    # Para un lote específico
    generar_reporte_maduracion_paltas(lote_id=42)
    
    # Para un producto específico
    generar_reporte_maduracion_paltas(producto_id=5)
    
    # Para un pallet específico por su código QR
    generar_reporte_maduracion_paltas(pallet_id='LOT-12345')
    
    # Para un calibre específico
    generar_reporte_maduracion_paltas(calibre='70')
    
    # Para un estado de maduración específico
    generar_reporte_maduracion_paltas(estado_maduracion='maduro')
    
    # Combinación de filtros
    generar_reporte_maduracion_paltas(business_id=1, estado_maduracion='verde')
    """
    # Construir el filtro base
    query = Q()
    
    # Si no hay filtros específicos de lote/producto/pallet/calibre, mostrar solo paltas
    if not any([lote_id, producto_id, pallet_id, calibre]):
        query = Q(producto__nombre__icontains='palta') | Q(producto__nombre__icontains='aguacate')
    
    # Aplicar filtros específicos si existen
    if business_id:
        query &= Q(business_id=business_id)
    if lote_id:
        query &= Q(id=lote_id)
    if producto_id:
        query &= Q(producto_id=producto_id)
    if pallet_id:
        query &= Q(qr_code=pallet_id)
    if calibre:
        query &= Q(calibre=calibre)
    if estado_maduracion:
        query &= Q(estado_maduracion=estado_maduracion)
    
    palta_lotes = FruitLot.objects.filter(query).select_related('producto', 'box_type', 'pallet_type')
    
    if not palta_lotes.exists():
        print("No se encontraron lotes de paltas en el sistema.")
        return
    
    # Estadísticas por estado de maduración
    maduracion_stats = palta_lotes.values('estado_maduracion').annotate(
        total_lotes=Count('id'),
        total_cajas=Sum('cantidad_cajas'),
        peso_bruto_total=Sum('peso_bruto'),
        peso_neto_total=Sum('peso_neto')
    ).order_by('estado_maduracion')
    
    # Historial de cambios de maduración recientes
    historial_reciente = MadurationHistory.objects.filter(
        lote__in=palta_lotes
    ).select_related('lote', 'lote__producto').order_by('-fecha_cambio')[:20]
    
    # Calcular métricas de tiempo promedio en cada estado
    tiempo_maduracion = []
    for lote in palta_lotes:
        historial = MadurationHistory.objects.filter(lote=lote).order_by('fecha_cambio')
        if historial.count() > 1:
            estados = list(historial.values_list('estado_maduracion', 'fecha_cambio'))
            for i in range(len(estados) - 1):
                tiempo_maduracion.append({
                    'lote_id': lote.id,
                    'estado': estados[i][0],
                    'dias': (estados[i+1][1] - estados[i][1]).days
                })
    
    # Agrupar por días en cada estado
    tiempo_promedio = {}
    for item in tiempo_maduracion:
        estado = item['estado']
        if estado not in tiempo_promedio:
            tiempo_promedio[estado] = {'total_dias': 0, 'conteo': 0}
        
        tiempo_promedio[estado]['total_dias'] += item['dias']
        tiempo_promedio[estado]['conteo'] += 1
    
    for estado, datos in tiempo_promedio.items():
        if datos['conteo'] > 0:
            datos['promedio'] = datos['total_dias'] / datos['conteo']
    
    # Calcular datos adicionales para cada lote
    lotes_data = []
    costo_almacenaje_total = 0
    costo_total = 0
    perdida_estimada_total = 0
    
    for lote in palta_lotes:
        # Calcular días en bodega
        dias_en_bodega = (timezone.now().date() - lote.fecha_ingreso).days
        
        # Calcular porcentaje de maduración basado en estado y días
        porcentaje_maduracion = 0
        if lote.estado_maduracion == 'verde':
            porcentaje_maduracion = min(25, dias_en_bodega * 2)  # Máximo 25%
        elif lote.estado_maduracion == 'pre-maduro':
            porcentaje_maduracion = min(75, 25 + (dias_en_bodega * 3))  # Entre 25% y 75%
        elif lote.estado_maduracion == 'maduro':
            porcentaje_maduracion = min(90, 75 + (dias_en_bodega * 2))  # Entre 75% y 90%
        elif lote.estado_maduracion == 'sobremaduro':
            porcentaje_maduracion = min(100, 90 + dias_en_bodega)  # Entre 90% y 100%
        
        # Calcular pérdida estimada basada en porcentaje de pérdida y peso neto
        perdida_estimada = float(lote.peso_neto) * (float(lote.porcentaje_perdida_estimado) / 100)
        perdida_estimada_total += perdida_estimada
        
        # Calcular costo de almacenaje acumulado
        costo_almacenaje = float(lote.costo_diario_almacenaje) * dias_en_bodega
        costo_almacenaje_total += costo_almacenaje
        
        # Calcular costo total (inicial + almacenaje)
        costo_lote_total = float(lote.costo_inicial) + costo_almacenaje
        costo_total += costo_lote_total
        
        # Calcular peso disponible (restando reservas)
        peso_reservado = lote.reservas.filter(estado='confirmada').aggregate(
            total=Sum('cantidad_kg')
        )['total'] or 0
        peso_disponible = float(lote.peso_neto) - float(peso_reservado)
        
        lote_data = {
            'id': lote.id,
            'producto': lote.producto.nombre,
            'calibre': lote.calibre,
            'estado_maduracion': lote.estado_maduracion,
            'porcentaje_maduracion': porcentaje_maduracion,
            'cantidad_cajas': lote.cantidad_cajas,
            'peso_neto': float(lote.peso_neto),
            'peso_disponible': peso_disponible,
            'perdida_estimada': perdida_estimada,
            'dias_en_bodega': dias_en_bodega,
            'costo_almacenaje': costo_almacenaje,
            'costo_total': costo_lote_total
        }
        
        lotes_data.append(lote_data)
    
    # Imprimir resultados en formato legible
    print("\n" + "="*80)
    print(" "*30 + "REPORTE DE MADURACIÓN DE PALTAS")
    print("="*80)
    
    print("\n[1] RESUMEN GENERAL")
    print("-"*40)
    print(f"Total de lotes de paltas: {palta_lotes.count()}")
    print(f"Total de cajas: {palta_lotes.aggregate(Sum('cantidad_cajas'))['cantidad_cajas__sum'] or 0}")
    print(f"Peso neto total: {palta_lotes.aggregate(Sum('peso_neto'))['peso_neto__sum'] or 0} kg")
    print(f"Costo inicial total: ${palta_lotes.aggregate(Sum('costo_inicial'))['costo_inicial__sum'] or 0:,.2f}")
    print(f"Costo de almacenaje acumulado: ${costo_almacenaje_total:,.2f}")
    print(f"Costo total: ${costo_total:,.2f}")
    print(f"Pérdida estimada total: {perdida_estimada_total:.2f} kg (${perdida_estimada_total * 2000:,.2f} aprox.)")
    
    print("\n[2] ESTADÍSTICAS POR ESTADO DE MADURACIÓN")
    print("-"*40)
    for stat in maduracion_stats:
        print(f"Estado: {stat['estado_maduracion']}")
        print(f"  - Lotes: {stat['total_lotes']}")
        print(f"  - Cajas: {stat['total_cajas']}")
        print(f"  - Peso neto: {stat['peso_neto_total']} kg")
        print()
    
    print("\n[3] TIEMPO PROMEDIO EN CADA ESTADO")
    print("-"*40)
    for estado, datos in tiempo_promedio.items():
        if datos['conteo'] > 0:
            print(f"Estado: {estado}")
            print(f"  - Promedio de días: {datos['promedio']:.1f}")
            print(f"  - Basado en {datos['conteo']} transiciones")
            print()
    
    print("\n[4] HISTORIAL RECIENTE DE CAMBIOS DE MADURACIÓN")
    print("-"*40)
    for h in historial_reciente:
        estado_anterior = h.lote.maduration_history.filter(
            fecha_cambio__lt=h.fecha_cambio
        ).order_by('-fecha_cambio').first()
        
        estado_anterior_str = estado_anterior.estado_maduracion if estado_anterior else "inicial"
        
        print(f"Lote #{h.lote.id} - {h.lote.producto.nombre}")
        print(f"  - Cambio: {estado_anterior_str} → {h.estado_maduracion}")
        print(f"  - Fecha: {h.fecha_cambio}")
        print(f"  - Hace {(timezone.now().date() - h.fecha_cambio).days} días")
        print()
    
    print("\n[5] DETALLE DE LOTES")
    print("-"*40)
    for lote_data in lotes_data[:10]:  # Limitamos a 10 para no saturar la consola
        print(f"Lote #{lote_data['id']} - {lote_data['producto']}")
        print(f"  - Calibre: {lote_data['calibre']}")
        print(f"  - Estado: {lote_data['estado_maduracion']} ({lote_data['porcentaje_maduracion']}% de maduración)")
        print(f"  - Cajas: {lote_data['cantidad_cajas']}")
        print(f"  - Peso neto: {lote_data['peso_neto']:.2f} kg")
        print(f"  - Peso disponible: {lote_data['peso_disponible']:.2f} kg")
        print(f"  - Días en bodega: {lote_data['dias_en_bodega']} días")
        print(f"  - Costo almacenaje: ${lote_data['costo_almacenaje']:,.2f}")
        print(f"  - Costo total: ${lote_data['costo_total']:,.2f}")
        print(f"  - Pérdida estimada: {lote_data['perdida_estimada']:.2f} kg")
        print()
    
    if len(lotes_data) > 10:
        print(f"... y {len(lotes_data) - 10} lotes más.")
    
    print("\n" + "="*80)
    print(" "*25 + "FIN DEL REPORTE DE MADURACIÓN DE PALTAS")
    print("="*80 + "\n")
    
    # Preparar datos para retornar
    return {
        'lotes': lotes_data,
        'estadisticas_maduracion': list(maduracion_stats),
        'tiempo_promedio_estados': tiempo_promedio,
        'historial_reciente': [
            {
                'lote_id': h.lote.id,
                'producto': h.lote.producto.nombre,
                'estado_anterior': h.lote.maduration_history.filter(
                    fecha_cambio__lt=h.fecha_cambio
                ).order_by('-fecha_cambio').first().estado_maduracion if h.lote.maduration_history.filter(
                    fecha_cambio__lt=h.fecha_cambio
                ).exists() else 'inicial',
                'estado_nuevo': h.estado_maduracion,
                'fecha_cambio': h.fecha_cambio.strftime('%Y-%m-%d'),
                'dias_desde_cambio': (timezone.now().date() - h.fecha_cambio).days
            }
            for h in historial_reciente
        ],
        'resumen': {
            'total_lotes': palta_lotes.count(),
            'total_cajas': palta_lotes.aggregate(Sum('cantidad_cajas'))['cantidad_cajas__sum'] or 0,
            'peso_neto_total': float(palta_lotes.aggregate(Sum('peso_neto'))['peso_neto__sum'] or 0),
            'costo_inicial_total': float(palta_lotes.aggregate(Sum('costo_inicial'))['costo_inicial__sum'] or 0),
            'costo_almacenaje_total': costo_almacenaje_total,
            'costo_total': costo_total,
            'perdida_estimada_total': perdida_estimada_total
        }
    }
