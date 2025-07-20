import os
import sys
import django
from decimal import Decimal
from datetime import datetime, timedelta

# Configurar entorno Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from inventory.models import FruitLot, Product
from django.db.models import F, ExpressionWrapper, DecimalField
from django.utils import timezone


def calculate_maduration_price(lote):
    """
    Calcula el precio recomendado basado en la maduración y pérdida estimada.
    
    Estrategia de precios:
    - Objetivo: Ganar siempre 500 pesos por kilo cuando sea posible
    - Ajustar precio según maduración y pérdida
    - Para sobremaduros: minimizar pérdidas, incluso vendiendo al costo si es necesario
    
    El costo real aumenta con la maduración debido a la pérdida de producto.
    """
    # Costo inicial por kilo (al momento de la compra)
    costo_inicial_kg = lote.costo_inicial / lote.peso_neto if lote.peso_neto else Decimal('0')
    
    # Costo de almacenaje acumulado
    from datetime import date
    dias = (date.today() - lote.fecha_ingreso).days
    costo_almacenaje_total = lote.costo_diario_almacenaje * dias
    
    # Calcular el costo real considerando la pérdida por maduración
    # Si pierdo X% del producto, el costo por kilo del producto restante aumenta
    factor_ajuste_perdida = Decimal('1.00')
    if lote.porcentaje_perdida_estimado > 0:
        # Si pierdo 5% del producto, el costo por kilo aumenta en aproximadamente 5.26%
        # Fórmula: 1 / (1 - % pérdida)
        factor_ajuste_perdida = Decimal('1.00') / (Decimal('1.00') - (lote.porcentaje_perdida_estimado / Decimal('100.00')))
    
    # Costo real por kilo considerando pérdida
    costo_real_kg = (costo_inicial_kg + (costo_almacenaje_total / lote.peso_neto)) * factor_ajuste_perdida
    
    # Margen fijo de 500 pesos por kilo
    margen_fijo = Decimal('500')
    
    # Precio base: costo real + margen fijo
    precio_base = costo_real_kg + margen_fijo
    
    # Ajuste según estado de maduración
    if lote.estado_maduracion == 'verde':
        # Para producto verde, podemos mantener precio alto
        precio_recomendado = precio_base
        ganancia_objetivo = margen_fijo
    elif lote.estado_maduracion == 'pre-maduro':
        # Para pre-maduro, mantener el margen fijo
        precio_recomendado = precio_base
        ganancia_objetivo = margen_fijo
    elif lote.estado_maduracion == 'maduro':
        # Para maduro (punto óptimo), podemos aumentar un poco el precio
        precio_recomendado = precio_base * Decimal('1.05')  # +5%
        ganancia_objetivo = margen_fijo * Decimal('1.05')
    elif lote.estado_maduracion == 'sobremaduro':
        # Para sobremaduro, reducir precio para vender rápido
        dias_sobremaduro = max(0, (timezone.now().date() - lote.fecha_maduracion).days if lote.fecha_maduracion else 0)
        
        # Reducir el margen según los días de sobremaduración
        # Día 1: 80% del margen, Día 2: 60%, Día 3: 40%, Día 4: 20%, Día 5+: 0%
        factor_reduccion = max(Decimal('0'), Decimal('1.0') - (Decimal('0.2') * dias_sobremaduro))
        ganancia_objetivo = margen_fijo * factor_reduccion
        
        # Si el producto está muy sobremaduro (más de 5 días), vender al costo o con pérdida mínima
        if dias_sobremaduro > 5:
            # Intentar recuperar al menos el 90% del costo
            precio_recomendado = costo_real_kg * Decimal('0.9')
            ganancia_objetivo = precio_recomendado - costo_real_kg  # Negativo (pérdida)
        else:
            precio_recomendado = costo_real_kg + ganancia_objetivo
    else:
        precio_recomendado = precio_base
        ganancia_objetivo = margen_fijo
    
    # Para paltas específicamente, ajustar según calibre
    producto_nombre = lote.producto.nombre.lower() if lote.producto else ""
    if "palta" in producto_nombre or "aguacate" in producto_nombre:
        calibre = lote.calibre
        # Precios base por calibre (referencia)
        precios_base_calibre = {
            '12': Decimal('2150'),
            '14': Decimal('2050'),
            '16': Decimal('1950'),
            '20': Decimal('1850'),
            '26': Decimal('1750'),
            '32': Decimal('1250')
        }
        
        # Si el precio calculado es muy diferente del precio base de referencia para el calibre,
        # ajustarlo para que no se aleje demasiado del mercado
        if calibre in precios_base_calibre:
            precio_referencia = precios_base_calibre[calibre]
            
            # Si el precio calculado es más de 20% mayor que el precio de referencia,
            # limitarlo al precio de referencia + 20%
            if precio_recomendado > precio_referencia * Decimal('1.2'):
                precio_recomendado = precio_referencia * Decimal('1.2')
                ganancia_objetivo = precio_recomendado - costo_real_kg
            
            # Si el precio calculado es más de 30% menor que el precio de referencia,
            # y no es sobremaduro con más de 5 días, limitarlo al precio de referencia - 30%
            if precio_recomendado < precio_referencia * Decimal('0.7') and not (
                lote.estado_maduracion == 'sobremaduro' and 
                ((timezone.now().date() - lote.fecha_maduracion).days if lote.fecha_maduracion else 0) > 5
            ):
                precio_recomendado = precio_referencia * Decimal('0.7')
                ganancia_objetivo = precio_recomendado - costo_real_kg
    
    # Calcular margen final (puede ser negativo para sobremaduros)
    margen_final = precio_recomendado - costo_real_kg
    margen_porcentaje = (margen_final / costo_real_kg) if costo_real_kg else Decimal('0')
    
    return {
        'precio_recomendado_kg': precio_recomendado.quantize(Decimal('0.01')),
        'costo_real_kg': costo_real_kg.quantize(Decimal('0.01')),
        'costo_inicial_kg': costo_inicial_kg.quantize(Decimal('0.01')),
        'factor_ajuste_perdida': factor_ajuste_perdida.quantize(Decimal('0.0001')),
        'ganancia_kg': margen_final.quantize(Decimal('0.01')),
        'margen_estimado': margen_porcentaje.quantize(Decimal('0.01')),
        'porcentaje_perdida': lote.porcentaje_perdida_estimado,
        'estado': lote.estado_maduracion
    }


def update_maduration_states():
    """
    Actualiza los estados de maduración basados en días transcurridos.
    
    Para paltas:
    - 0-3 días: Verde
    - 4-6 días: Pre-maduro
    - 7-10 días: Maduro
    - 11+ días: Sobremaduro
    
    Diferentes frutas tienen diferentes tiempos de maduración.
    """
    today = timezone.now().date()
    
    # Obtener todos los lotes activos
    lotes = FruitLot.objects.filter(
        cantidad_cajas__gt=0,  # Solo lotes con inventario
        peso_neto__gt=0
    ).select_related('producto')
    
    for lote in lotes:
        dias_desde_ingreso = (today - lote.fecha_ingreso).days
        producto_nombre = lote.producto.nombre.lower() if lote.producto else ""
        
        # Configuración específica para paltas
        if "palta" in producto_nombre or "aguacate" in producto_nombre:
            if dias_desde_ingreso <= 3:
                nuevo_estado = 'verde'
            elif dias_desde_ingreso <= 6:
                nuevo_estado = 'pre-maduro'
            elif dias_desde_ingreso <= 10:
                nuevo_estado = 'maduro'
            else:
                nuevo_estado = 'sobremaduro'
                if not lote.fecha_maduracion:
                    lote.fecha_maduracion = today - timedelta(days=dias_desde_ingreso - 10)
        
        # Configuración para otras frutas (más lenta)
        else:
            if dias_desde_ingreso <= 5:
                nuevo_estado = 'verde'
            elif dias_desde_ingreso <= 10:
                nuevo_estado = 'pre-maduro'
            elif dias_desde_ingreso <= 15:
                nuevo_estado = 'maduro'
            else:
                nuevo_estado = 'sobremaduro'
                if not lote.fecha_maduracion:
                    lote.fecha_maduracion = today - timedelta(days=dias_desde_ingreso - 15)
        
        # Actualizar estado si ha cambiado
        if lote.estado_maduracion != nuevo_estado:
            # Registrar cambio en historial
            from inventory.models import MadurationHistory
            MadurationHistory.objects.create(
                lote=lote,
                estado_maduracion=nuevo_estado
                # fecha_cambio se establece automáticamente con auto_now_add=True
            )
            
            # Actualizar lote
            lote.estado_maduracion = nuevo_estado
            if nuevo_estado == 'sobremaduro' and not lote.fecha_maduracion:
                lote.fecha_maduracion = today
            
            # Para paltas, actualizar porcentaje de pérdida estimado
            if "palta" in producto_nombre or "aguacate" in producto_nombre:
                if nuevo_estado == 'pre-maduro':
                    lote.porcentaje_perdida_estimado = Decimal('2.00')  # 2% de pérdida
                elif nuevo_estado == 'maduro':
                    lote.porcentaje_perdida_estimado = Decimal('5.00')  # 5% de pérdida
                elif nuevo_estado == 'sobremaduro':
                    # Aumenta 3% por día de sobremaduración
                    dias_sobremaduro = (today - lote.fecha_maduracion).days if lote.fecha_maduracion else 1
                    lote.porcentaje_perdida_estimado = min(
                        Decimal('40.00'),  # Máximo 40% de pérdida
                        Decimal('5.00') + (Decimal('3.00') * dias_sobremaduro)
                    )
            
            lote.save()


def generate_pricing_report():
    """
    Genera un reporte de precios recomendados para todos los lotes activos.
    Incluye la ganancia objetivo de 500 pesos por kilo cuando es posible.
    """
    # Primero actualizar estados de maduración
    update_maduration_states()
    
    # Obtener lotes activos
    lotes = FruitLot.objects.filter(
        cantidad_cajas__gt=0,
        peso_neto__gt=0
    ).select_related('producto', 'business', 'box_type')
    
    report = []
    
    for lote in lotes:
        pricing_data = calculate_maduration_price(lote)
        
        report.append({
            'lote_id': lote.id,
            'producto': lote.producto.nombre if lote.producto else "Desconocido",
            'calibre': lote.calibre,
            'business': lote.business.nombre,
            'estado_maduracion': lote.estado_maduracion,
            'dias_desde_ingreso': (timezone.now().date() - lote.fecha_ingreso).days,
            'cantidad_cajas': lote.cantidad_cajas,
            'peso_neto': float(lote.peso_neto),
            'porcentaje_perdida': float(lote.porcentaje_perdida_estimado),
            'precio_recomendado_kg': float(pricing_data['precio_recomendado_kg']),
            'costo_real_kg': float(pricing_data['costo_real_kg']),
            'costo_inicial_kg': float(pricing_data['costo_inicial_kg']),
            'ganancia_kg': float(pricing_data['ganancia_kg']),
            'factor_ajuste_perdida': float(pricing_data['factor_ajuste_perdida']),
            'margen_estimado': float(pricing_data['margen_estimado'])
        })
    
    return report


if __name__ == '__main__':
    print("Generando reporte de precios basados en maduración...")
    report = generate_pricing_report()
    
    # Agrupar por tipo de producto para mejor visualización
    productos = {}
    for item in report:
        producto = item['producto']
        if producto not in productos:
            productos[producto] = []
        productos[producto].append(item)
    
    # Mostrar reporte
    print("\nREPORTE DE PRECIOS RECOMENDADOS POR MADURACIÓN")
    print("=" * 120)
    
    for producto, items in productos.items():
        print(f"\n\033[1m{producto.upper()} - {items[0]['business']}\033[0m")
        print("-" * 120)
        print(f"{'ID':^5} | {'Calibre':^7} | {'Estado':^12} | {'Días':^5} | {'Cajas':^5} | {'Kg':^8} | {'Pérdida %':^9} | "
              f"{'Precio Rec.':^10} | {'Costo Real':^10} | {'Ganancia':^9} | {'Objetivo':^9} | {'Factor':^6} | {'Margen':^6}")
        print("-" * 120)
        
        # Ordenar por calibre y estado de maduración
        items.sort(key=lambda x: (x['calibre'], ['verde', 'pre-maduro', 'maduro', 'sobremaduro'].index(x['estado_maduracion'])))
        
        for item in items:
            # Colorear según estado de maduración
            if item['estado_maduracion'] == 'verde':
                color = '\033[92m'  # Verde
            elif item['estado_maduracion'] == 'pre-maduro':
                color = '\033[93m'  # Amarillo
            elif item['estado_maduracion'] == 'maduro':
                color = '\033[33m'  # Naranja
            else:  # sobremaduro
                color = '\033[91m'  # Rojo
            
            # Colorear ganancia
            if item['ganancia_kg'] >= 500:
                color_ganancia = '\033[92m'  # Verde para ganancia objetivo o mayor
            elif item['ganancia_kg'] >= 0:
                color_ganancia = '\033[93m'  # Amarillo para ganancia positiva pero menor al objetivo
            else:
                color_ganancia = '\033[91m'  # Rojo para pérdida
            
            reset = '\033[0m'
            
            # Calcular objetivo de ganancia (500 pesos por defecto)
            objetivo = 500
            if item['estado_maduracion'] == 'maduro':
                objetivo = 525  # 5% extra para maduro
            elif item['estado_maduracion'] == 'sobremaduro':
                dias_sobremaduro = max(0, item['dias_desde_ingreso'] - 7)  # Estimación
                objetivo = max(0, 500 - (100 * dias_sobremaduro))
            
            print(f"{item['lote_id']:^5} | {item['calibre']:^7} | {color}{item['estado_maduracion']:^12}{reset} | "
                  f"{item['dias_desde_ingreso']:^5} | {item['cantidad_cajas']:^5} | {item['peso_neto']:^8.2f} | "
                  f"{item['porcentaje_perdida']:^9.2f} | {item['precio_recomendado_kg']:^10.2f} | "
                  f"{item['costo_real_kg']:^10.2f} | {color_ganancia}{item['ganancia_kg']:^9.2f}{reset} | "
                  f"{objetivo:^9.0f} | {item['factor_ajuste_perdida']:^6.4f} | {item['margen_estimado']:^6.2f}")
    
    print("=" * 120)
    print(f"Total de lotes: {len(report)}")
    
    # Mostrar resumen por calibre para paltas
    palta_items = [item for producto, items in productos.items() 
                  for item in items if 'palta' in producto.lower()]
    
    if palta_items:
        print("\n\033[1mRESUMEN POR CALIBRE DE PALTAS\033[0m")
        print("-" * 100)
        print(f"{'Calibre':^7} | {'Precio Base':^11} | {'Precio Prom.':^12} | {'Costo Prom.':^11} | {'Ganancia Prom.':^14} | {'% Objetivo':^10} | {'Lotes':^5}")
        print("-" * 100)
        
        calibres = {}
        for item in palta_items:
            calibre = item['calibre']
            if calibre not in calibres:
                calibres[calibre] = {
                    'precio_total': 0,
                    'costo_total': 0,
                    'ganancia_total': 0,
                    'count': 0
                }
            
            calibres[calibre]['precio_total'] += item['precio_recomendado_kg']
            calibres[calibre]['costo_total'] += item['costo_real_kg']
            calibres[calibre]['ganancia_total'] += item['ganancia_kg']
            calibres[calibre]['count'] += 1
        
        # Definir precios base por calibre
        precios_base = {
            '12': 2150,
            '14': 2050,
            '16': 1950,
            '20': 1850,
            '26': 1750,
            '32': 1250
        }
        
        # Ordenar calibres (pueden ser numéricos o alfanuméricos)
        def ordenar_calibre(calibre):
            # Intentar convertir a entero si es posible, de lo contrario usar el valor original
            try:
                return int(calibre)
            except ValueError:
                # Para calibres como '1ra', '2da', etc. asignar valores de ordenamiento
                if calibre == '1ra':
                    return 1000
                elif calibre == '2da':
                    return 2000
                elif calibre == '3ra':
                    return 3000
                elif calibre == '4ta':
                    return 4000
                elif calibre == 'Extra':
                    return 5000
                elif calibre == 'Super Extra':
                    return 6000
                else:
                    return 9999  # Otros calibres al final
        
        for calibre in sorted(calibres.keys(), key=ordenar_calibre):
            data = calibres[calibre]
            precio_prom = data['precio_total'] / data['count']
            costo_prom = data['costo_total'] / data['count']
            ganancia_prom = data['ganancia_total'] / data['count']
            precio_base = precios_base.get(calibre, 0)
            
            # Calcular porcentaje del objetivo (500 pesos)
            porcentaje_objetivo = (ganancia_prom / 500) * 100
            
            # Colorear porcentaje objetivo
            if porcentaje_objetivo >= 100:
                color_objetivo = '\033[92m'  # Verde
            elif porcentaje_objetivo >= 0:
                color_objetivo = '\033[93m'  # Amarillo
            else:
                color_objetivo = '\033[91m'  # Rojo
            
            reset = '\033[0m'
            
            print(f"{calibre:^7} | {precio_base:^11.2f} | {precio_prom:^12.2f} | {costo_prom:^11.2f} | "
                  f"{ganancia_prom:^14.2f} | {color_objetivo}{porcentaje_objetivo:^10.2f}%{reset} | {data['count']:^5}")
        
        print("-" * 100)
