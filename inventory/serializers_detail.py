from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum
from .models import FruitLot, MadurationHistory
from sales.models import Sale
from datetime import date

class LotMovementSerializer(serializers.Serializer):
    """
    Serializer para representar movimientos de un lote (cambios de estado, ventas, etc.)
    """
    id = serializers.IntegerField()
    fecha = serializers.DateTimeField()
    tipo = serializers.CharField()
    estado_anterior = serializers.CharField(allow_null=True)
    estado_nuevo = serializers.CharField(allow_null=True)
    cantidad = serializers.FloatField(allow_null=True)
    usuario = serializers.CharField()
    notas = serializers.CharField(allow_null=True)


class LotPriceHistorySerializer(serializers.Serializer):
    """
    Serializer para representar el historial de precios de un lote
    """
    id = serializers.IntegerField()
    fecha = serializers.DateTimeField()
    precio = serializers.FloatField()
    usuario = serializers.CharField()
    notas = serializers.CharField(allow_null=True)


class FruitLotDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para un lote de fruta, siguiendo exactamente la estructura solicitada
    """
    # Información básica del lote
    id = serializers.IntegerField(source='pk')
    uid = serializers.UUIDField()
    codigo = serializers.CharField(source='qr_code')
    
    # Información agrupada en objetos
    producto = serializers.SerializerMethodField()
    origen = serializers.SerializerMethodField()
    fechas = serializers.SerializerMethodField()
    inventario = serializers.SerializerMethodField()
    maduracion = serializers.SerializerMethodField()
    precios = serializers.SerializerMethodField()
    metricas = serializers.SerializerMethodField()
    
    # Valores de llegada y comparación
    valores_llegada = serializers.SerializerMethodField()
    comparacion_venta = serializers.SerializerMethodField()
    
    # Recomendaciones del sistema
    recomendaciones = serializers.SerializerMethodField()
    
    # Historial de movimientos y precios
    movimientos = serializers.SerializerMethodField()
    historial_precios = serializers.SerializerMethodField()
    
    def get_producto(self, obj):
        return {
            'id': obj.producto.id if obj.producto else None,
            'nombre': obj.producto.nombre if obj.producto else None,
            'marca': obj.marca,
            'tipo': self.get_tipo_producto(obj)
        }
    
    def get_origen(self, obj):
        return {
            'proveedor_id': self.get_proveedor_id(obj),
            'proveedor': obj.proveedor,
            'procedencia': obj.procedencia,
            'pais': obj.pais
        }
    
    def get_fechas(self, obj):
        return {
            'recepcion': obj.fecha_ingreso,
            'maduracion': obj.fecha_maduracion,
            'dias_en_inventario': self.get_dias_en_inventario(obj),
            'dias_desde_ingreso': self.get_dias_desde_ingreso(obj),
            'dias_en_bodega': self.get_dias_en_bodega(obj)
        }
    
    def get_inventario(self, obj):
        return {
            'cantidad_cajas_inicial': obj.cantidad_cajas,
            'cantidad_cajas_actual': self.get_cantidad_cajas_actual(obj),
            'box_type': obj.box_type.nombre if obj.box_type else None,
            'pallet_type': self.get_pallet_type(obj),
            'peso_bruto': obj.peso_bruto,
            'peso_neto': obj.peso_neto,
            'cantidad_inicial_kg': self.get_cantidad_inicial_kg(obj),
            'cantidad_actual_kg': self.get_cantidad_actual_kg(obj),
            'peso_disponible': self.get_peso_disponible(obj),
            'peso_reservado': self.get_peso_reservado(obj),
            'peso_vendible': self.get_peso_vendible(obj),
            'valor_inventario': self.get_valor_inventario(obj)
        }
    
    def get_maduracion(self, obj):
        return {
            'estado': obj.estado_maduracion,
            'ubicacion': self.get_ubicacion(obj)
        }
    
    def get_precios(self, obj):
        return {
            'precio_compra': obj.costo_inicial,
            'precio_actual': self.get_precio_actual(obj),
            'costo_diario_almacenaje': obj.costo_diario_almacenaje,
            'precio_recomendado_kg': self.get_precio_recomendado_kg(obj),
            'costo_real_kg': self.get_costo_real_kg(obj),
            'ganancia_kg': self.get_ganancia_kg(obj),
            'margen': self.get_margen(obj),
            'precio_sugerido_min': obj.precio_sugerido_min,
            'precio_sugerido_max': obj.precio_sugerido_max
        }
    
    def get_metricas(self, obj):
        return {
            'porcentaje_perdida': self.get_porcentaje_perdida(obj),
            'perdida_estimada': self.get_perdida_estimada(obj),
            'valor_perdida': self.get_valor_perdida(obj),
            'ingreso_estimado': self.get_ingreso_estimado(obj),
            'ganancia_total': self.get_ganancia_total(obj)
        }
    
    def get_recomendaciones(self, obj):
        return {
            'urgencia_venta': self.get_urgencia_venta(obj),
            'recomendacion': self.get_recomendacion(obj)
        }

    # Los campos ahora están agrupados en objetos anidados
    
    class Meta:
        model = FruitLot
        fields = (
            'id', 'uid', 'codigo',
            'producto', 'origen', 'fechas', 'inventario', 'maduracion',
            'precios', 'metricas', 'recomendaciones',
            'valores_llegada', 'comparacion_venta',
            'movimientos', 'historial_precios',
        )

    def get_tipo_producto(self, obj):
        nombre = (obj.producto.nombre if obj.producto else '').lower()
        if 'palta' in nombre or 'aguacate' in nombre:
            return 'palta'
        if 'mango' in nombre:
            return 'mango'
        if 'platano' in nombre or 'plátano' in nombre or 'banano' in nombre:
            return 'platano'
        return 'otro'

    def get_proveedor_id(self, obj):
        # En este caso, proveedor es un string, no un objeto relacionado
        # Devolvemos None o un ID ficticio según sea necesario
        return None

    def get_pallet_type(self, obj):
        if obj.pallet_type:
            return obj.pallet_type.nombre
        return None
        
    def get_cantidad_cajas_actual(self, obj):
        # Por defecto devolvemos la cantidad inicial de cajas
        # Este método podría ser modificado para calcular la cantidad actual
        # basado en ventas u otros movimientos
        return obj.cantidad_cajas
        
    def get_cantidad_inicial_kg(self, obj):
        tipo = self.get_tipo_producto(obj)
        if tipo == 'palta':
            return float(obj.peso_neto or 0)
        return None
        
    def get_cantidad_actual_kg(self, obj):
        tipo = self.get_tipo_producto(obj)
        if tipo == 'palta':
            return float(self.get_peso_disponible(obj))
        return None

    def get_peso_reservado(self, obj):
        from .models import StockReservation
        from sales.models import SalePendingItem
        
        # Reservas directas del lote
        reservas_directas = StockReservation.objects.filter(
            lote=obj,
            estado='en_proceso'
        ).aggregate(total=Sum('kg_reservados'))['total'] or 0
        
        # Reservas a través de ventas pendientes
        reservas_pendientes = SalePendingItem.objects.filter(
            lote=obj,
            venta_pendiente__estado='pendiente'
        ).aggregate(total=Sum('cantidad_kg'))['total'] or 0
        
        total = float(reservas_directas) + float(reservas_pendientes)
        return total

    def get_peso_disponible(self, obj):
        neto = float(obj.peso_neto or 0)
        reservado = self.get_peso_reservado(obj)
        return neto - reservado if neto > reservado else 0

    def get_peso_vendible(self, obj):
        disponible = self.get_peso_disponible(obj)
        perdida = self.get_perdida_estimada(obj)
        return disponible - perdida if disponible > perdida else 0

    def get_ubicacion(self, obj):
        # Este campo no existe en el modelo original, se podría implementar
        # según la lógica de negocio o devolver un valor por defecto
        return "Bodega principal"

    def get_precio_actual(self, obj):
        return float(obj.costo_actualizado())

    def get_dias_en_inventario(self, obj):
        if obj.fecha_ingreso:
            return (date.today() - obj.fecha_ingreso).days
        return 0

    def get_dias_desde_ingreso(self, obj):
        if obj.fecha_ingreso:
            return (date.today() - obj.fecha_ingreso).days
        return 0

    def get_dias_en_bodega(self, obj):
        return self.get_dias_desde_ingreso(obj)
        
    def get_valor_inventario(self, obj):
        tipo = self.get_tipo_producto(obj)
        if tipo == 'palta':
            # Para paltas: kilos netos * precio_actual
            return float(obj.peso_neto or 0) * float(self.get_precio_actual(obj))
        else:
            # Para otros: cantidad de cajas * precio_inicial
            return float(obj.cantidad_cajas or 0) * float(obj.costo_inicial or 0)

    def get_porcentaje_perdida(self, obj):
        """
        Calcula el porcentaje de pérdida basado en el tipo de producto y estado de maduración
        """
        tipo = self.get_tipo_producto(obj)
        estado = getattr(obj, 'estado_maduracion', 'verde')
        if tipo == 'palta':
            if estado == 'verde':
                return 2
            if estado == 'pre-maduro':
                return 3
            if estado == 'maduro':
                return 5
            if estado == 'sobremaduro':
                return 10
        return 0

    def get_perdida_estimada(self, obj):
        """
        Calcula la pérdida estimada basada en los valores iniciales del historial
        """
        try:
            # Obtenemos el primer registro del historial
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                peso_inicial = float(getattr(primer_registro, 'peso_neto', 0) or 0)
                
                # Calculamos la pérdida usando el peso inicial
                porcentaje = self.get_porcentaje_perdida(obj)
                return round(peso_inicial * (porcentaje/100), 2)
        except Exception:
            pass
            
        # Si no hay historial, usamos el método anterior como fallback
        neto = float(obj.peso_neto or 0)
        return round(neto * (self.get_porcentaje_perdida(obj)/100), 2)

    def get_valor_perdida(self, obj):
        """
        Calcula el valor de la pérdida basado en los valores iniciales del historial
        """
        try:
            # Obtenemos el primer registro del historial
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                
                # Obtenemos la pérdida estimada y el costo inicial
                perdida = self.get_perdida_estimada(obj)
                costo_inicial = float(getattr(primer_registro, 'costo_inicial', 0) or 0)
                
                return round(perdida * costo_inicial, 2)
        except Exception:
            pass
            
        # Si no hay historial, usamos el método anterior como fallback
        perdida = self.get_perdida_estimada(obj)
        costo_actual = float(self.get_precio_actual(obj) or 0)
        return round(perdida * costo_actual, 2)

    def get_precio_recomendado_kg(self, obj):
        costo_real = self.get_costo_real_kg(obj)
        return round(costo_real * 1.3, 2)

    def get_costo_real_kg(self, obj):
        return float(obj.costo_inicial or 0)

    def get_ganancia_kg(self, obj):
        return round(self.get_precio_recomendado_kg(obj) - self.get_costo_real_kg(obj), 2)

    def get_margen(self, obj):
        costo = self.get_costo_real_kg(obj)
        if costo > 0:
            return round((self.get_ganancia_kg(obj) / costo) * 100, 2)
        return 25.0

    def get_ingreso_estimado(self, obj):
        """
        Calcula el ingreso estimado basado en los valores iniciales del pallet
        obtenidos del historial.
        """
        try:
            # Obtenemos el primer registro del historial
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                peso_inicial = float(getattr(primer_registro, 'peso_neto', 0) or 0)
                
                # Calculamos el precio recomendado basado en el costo inicial
                costo_inicial = float(getattr(primer_registro, 'costo_inicial', 0) or 0)
                precio_recomendado = round(costo_inicial * 1.3, 2)  # 30% de margen
                
                return round(precio_recomendado * peso_inicial, 2)
        except Exception:
            pass
            
        # Si no hay historial, usamos el método anterior como fallback
        peso_real = self.get_peso_vendible(obj)
        return round(self.get_precio_recomendado_kg(obj) * peso_real, 2)

    def get_ganancia_total(self, obj):
        """
        Calcula la ganancia total estimada basada en los valores iniciales del pallet
        obtenidos del historial.
        """
        try:
            # Obtenemos el primer registro del historial
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                peso_inicial = float(getattr(primer_registro, 'peso_neto', 0) or 0)
                
                # Calculamos el costo y precio iniciales
                costo_inicial = float(getattr(primer_registro, 'costo_inicial', 0) or 0)
                precio_recomendado = round(costo_inicial * 1.3, 2)  # 30% de margen
                
                # Ganancia por kg
                ganancia_kg = precio_recomendado - costo_inicial
                
                return round(ganancia_kg * peso_inicial, 2)
        except Exception:
            pass
            
        # Si no hay historial, usamos el método anterior como fallback
        peso_real = self.get_peso_vendible(obj)
        return round(self.get_ganancia_kg(obj) * peso_real, 2)

    def get_urgencia_venta(self, obj):
        estado = getattr(obj, 'estado_maduracion', 'verde')
        if estado == 'maduro':
            return 'alta'
        if estado == 'sobremaduro':
            return 'critica'
        return 'baja'

    def get_recomendacion(self, obj):
        estado = getattr(obj, 'estado_maduracion', 'verde')
        precio = self.get_precio_recomendado_kg(obj)
        if estado == 'verde':
            return {
                'accion': 'esperar',
                'mensaje': 'Mantener en cámara de maduración controlada. Revisar en 3 días.',
                'precio_sugerido': precio
            }
        elif estado == 'pre-maduro':
            return {
                'accion': 'preparar_venta',
                'mensaje': 'Preparar para venta en 2 días.',
                'precio_sugerido': precio
            }
        elif estado == 'maduro':
            return {
                'accion': 'vender',
                'mensaje': 'Vender lo antes posible.',
                'precio_sugerido': precio
            }
        elif estado == 'sobremaduro':
            return {
                'accion': 'liquidar',
                'mensaje': 'Liquidar stock urgentemente.',
                'precio_sugerido': precio
            }
        return None

    def get_movimientos(self, obj):
        """
        Genera un historial de movimientos basado en los cambios históricos del lote
        y las ventas asociadas.
        """
        movimientos = []
        
        # Obtener historial de cambios de estado de maduración
        maduration_history = MadurationHistory.objects.filter(lote__uid=obj.uid).order_by('fecha_cambio')
        
        for i, history in enumerate(maduration_history):
            estado_anterior = None
            if i > 0:
                estado_anterior = maduration_history[i-1].estado_maduracion
                
            movimientos.append({
                'id': i + 1,
                'fecha': history.fecha_cambio.isoformat() if hasattr(history.fecha_cambio, 'isoformat') else str(history.fecha_cambio),
                'tipo': 'cambio_maduracion',
                'estado_anterior': estado_anterior,
                'estado_nuevo': history.estado_maduracion,
                'cantidad': None,
                'usuario': 'Sistema',  # Podría mejorarse si se guarda el usuario que hizo el cambio
                'notas': None
            })
        
        # Obtener historial de ventas
        ventas = Sale.objects.filter(items__lote=obj).distinct()        
        for i, venta in enumerate(ventas):
            # Obtener el peso vendido desde los items de la venta
            peso_vendido = venta.items.filter(lote=obj).aggregate(total=Sum('peso_vendido'))['total'] or 0
            
            # Añadir la venta como un movimiento
            movimientos.append({
                'id': len(maduration_history) + i + 1,
                'fecha': venta.created_at.isoformat() if hasattr(venta.created_at, 'isoformat') else str(venta.created_at),
                'tipo': 'venta',
                'estado_anterior': None,
                'estado_nuevo': None,
                'cantidad': peso_vendido,
                'usuario': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip() if hasattr(venta, 'vendedor') and venta.vendedor else "Sistema",
                'notas': f"Venta #{venta.id} - {venta.cliente.nombre if venta.cliente else getattr(venta, 'nombre_cliente', 'Cliente no especificado')}"
            })
            
        # Ordenar movimientos por fecha
        movimientos = sorted(movimientos, key=lambda x: x['fecha'])
        
        # Renumerar IDs después de ordenar
        for i, mov in enumerate(movimientos):
            mov['id'] = i + 1
            
        return movimientos
        
    def get_valores_llegada(self, obj):
        """
        Obtiene los valores iniciales del pallet al momento de su llegada desde el historial.
        """
        # Obtener el primer registro histórico (el más antiguo)
        historicos = obj.history.all().order_by('history_date')
        primer_registro = historicos.first() if historicos.exists() else None
        
        if primer_registro:
            # Usar valores del primer registro histórico
            return {
                'fecha_ingreso': primer_registro.fecha_ingreso.isoformat() if hasattr(primer_registro.fecha_ingreso, 'isoformat') else str(primer_registro.fecha_ingreso),
                'peso_bruto_inicial': float(primer_registro.peso_bruto if primer_registro.peso_bruto else 0),
                'peso_neto_inicial': float(primer_registro.peso_neto if primer_registro.peso_neto else 0),
                'cantidad_cajas_inicial': primer_registro.cantidad_cajas,
                'costo_inicial': float(primer_registro.costo_inicial if primer_registro.costo_inicial else 0),
                'costo_por_kg_inicial': round(float(primer_registro.costo_inicial) / float(primer_registro.peso_neto), 2) 
                                        if primer_registro.peso_neto and float(primer_registro.peso_neto) > 0 else 0,
                'precio_sugerido_min': float(primer_registro.precio_sugerido_min) if primer_registro.precio_sugerido_min else None,
                'precio_sugerido_max': float(primer_registro.precio_sugerido_max) if primer_registro.precio_sugerido_max else None
            }
        else:
            # Fallback a los valores actuales si no hay historial
            return {
                'fecha_ingreso': obj.fecha_ingreso.isoformat() if hasattr(obj.fecha_ingreso, 'isoformat') else str(obj.fecha_ingreso),
                'peso_bruto_inicial': float(obj.peso_bruto if obj.peso_bruto else 0),
                'peso_neto_inicial': float(obj.peso_neto or 0),
                'cantidad_cajas_inicial': obj.cantidad_cajas,
                'costo_inicial': float(obj.costo_inicial if obj.costo_inicial else 0),
                'costo_por_kg_inicial': round(float(obj.costo_inicial) / float(obj.peso_neto), 2) if obj.peso_neto and float(obj.peso_neto) > 0 else 0,
                'precio_sugerido_min': float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None,
                'precio_sugerido_max': float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None
            }
    
    def get_historial_precios(self, obj):
        """
        Genera un historial de precios basado en las ventas del lote.
        """
        historial = []
        
        # Obtener items de venta para este lote
        from sales.models import SaleItem
        items_venta = SaleItem.objects.filter(lote=obj).select_related('venta').order_by('venta__created_at')
        
        for i, item in enumerate(items_venta):
            historial.append({
                'id': i + 1,
                'fecha': item.venta.created_at.isoformat() if hasattr(item.venta.created_at, 'isoformat') else str(item.venta.created_at),
                'precio': float(item.precio_kg) if item.precio_kg else 0,
                'peso_vendido': float(item.peso_vendido) if item.peso_vendido else 0,
                'usuario': f"{item.venta.vendedor.first_name} {item.venta.vendedor.last_name}".strip() if hasattr(item.venta, 'vendedor') and item.venta.vendedor else "Sistema",
                'notas': f"Venta #{item.venta.id} - {item.venta.cliente.nombre if item.venta.cliente else getattr(item.venta, 'nombre_cliente', 'Cliente no especificado')}"
            })
        
        # Si no hay ventas, agregar al menos el precio recomendado actual
        if not historial:
            historial.append({
                'id': 1,
                'fecha': timezone.now().isoformat(),
                'precio': self.get_precio_recomendado_kg(obj),
                'peso_vendido': 0,
                'usuario': "Sistema",
                'notas': "Precio recomendado inicial"
            })
        
        return historial
        
    def get_comparacion_venta(self, obj):
        """
        Compara los valores iniciales del pallet con los valores de venta total.
        """
        # Obtener ventas para calcular totales
        from sales.models import Sale
        ventas = Sale.objects.filter(items__lote=obj).distinct()
        
        # Calcular totales de venta con redondeo adecuado
        from sales.models import SaleItem
        items_lote = SaleItem.objects.filter(lote=obj)
        peso_total_vendido = round(sum(float(item.peso_vendido) for item in items_lote), 2)
        monto_total_ventas = round(sum(float(item.subtotal) for item in items_lote), 2)
        precio_promedio_kg = round(monto_total_ventas / peso_total_vendido, 2) if peso_total_vendido > 0 else 0
        
        # Obtener valores iniciales del historial
        try:
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                peso_neto_inicial = float(getattr(primer_registro, 'peso_neto', 0) or 0)
                costo_inicial = float(getattr(primer_registro, 'costo_inicial', 0) or 0)
            else:
                # Fallback a valores actuales
                peso_neto_inicial = float(obj.peso_neto or 0)
                costo_inicial = float(obj.costo_inicial or 0)
        except Exception:
            # Fallback a valores actuales en caso de error
            peso_neto_inicial = float(obj.peso_neto or 0)
            costo_inicial = float(obj.costo_inicial or 0)
        
        # Evitar división por cero
        if peso_neto_inicial <= 0:
            peso_neto_inicial = 1  # Valor mínimo para evitar división por cero
        
        # Calcular porcentajes y valores derivados
        porcentaje_vendido = round((peso_total_vendido / peso_neto_inicial) * 100, 2) if peso_neto_inicial > 0 else 0
        valor_total_inicial = round(costo_inicial, 2)
        valor_vendido = round(monto_total_ventas, 2)
        diferencia_valor = round(valor_vendido - valor_total_inicial, 2)
        porcentaje_diferencia = round((diferencia_valor / valor_total_inicial) * 100, 2) if valor_total_inicial > 0 else 0
        
        # Calcular costo por kg con validación
        costo_por_kg = round(costo_inicial / peso_neto_inicial, 2) if peso_neto_inicial > 0 else 0
        
        # Calcular diferencias y porcentajes con límites razonables
        diferencia_precio = round(precio_promedio_kg - costo_por_kg, 2)
        
        # Calcular porcentaje de margen con límites razonables
        if costo_por_kg > 0:
            porcentaje_margen = round((diferencia_precio / costo_por_kg) * 100, 2)
            # Limitar a un rango razonable para presentación (-100% a 1000%)
            porcentaje_margen = max(min(porcentaje_margen, 1000), -100)
        else:
            porcentaje_margen = 0
        
        # Calcular porcentaje vendido con límites razonables
        porcentaje_vendido = round((peso_total_vendido / peso_neto_inicial) * 100, 2)
        # Limitar a un máximo de 100% para presentación normal
        porcentaje_vendido = min(porcentaje_vendido, 100)
        
        # Calcular ganancia total de ventas reales (monto total de ventas - costo total del pallet)
        costo_total_pallet = float(round(obj.costo_actualizado() * obj.peso_neto, 2))  # Costo total inicial del pallet
        ganancia_total_ventas = round(float(monto_total_ventas) - costo_total_pallet, 2)
        
        return {
            'porcentaje_vendido': porcentaje_vendido,
            'peso_vendido': peso_total_vendido,
            'peso_inicial': peso_neto_inicial,
            'valor_inicial': valor_total_inicial,
            'valor_vendido': valor_vendido,
            'diferencia_valor': diferencia_valor,
            'porcentaje_diferencia': porcentaje_diferencia,
            'precio_promedio_kg': precio_promedio_kg,
            'costo_por_kg': costo_por_kg,
            'diferencia_precio': diferencia_precio,
            'porcentaje_margen': porcentaje_margen,
            'rentabilidad': 'positiva' if diferencia_precio > 0 else 'negativa' if diferencia_precio < 0 else 'neutra',
            'precio_dentro_rango': self._precio_dentro_rango(precio_promedio_kg, obj),
            'analisis': self._generar_analisis_venta(precio_promedio_kg, costo_por_kg, porcentaje_vendido, obj)
        }
        
    def _precio_dentro_rango(self, precio_promedio, obj):
        """
        Determina si el precio promedio está dentro del rango sugerido.
        """
        min_sugerido = float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None
        max_sugerido = float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None
        
        if min_sugerido is None or max_sugerido is None:
            return None
            
        if precio_promedio < min_sugerido:
            return 'porDebajo'
        elif precio_promedio > max_sugerido:
            return 'porEncima'
        else:
            return 'dentroRango'
            
    def _generar_analisis_venta(self, precio_promedio, costo_por_kg, porcentaje_vendido, obj):
        """
        Genera un análisis de la venta basado en precios y porcentaje vendido.
        """
        min_sugerido = float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None
        max_sugerido = float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None
        
        if porcentaje_vendido < 50:
            estado_venta = 'parcial'
        elif porcentaje_vendido < 90:
            estado_venta = 'mayoritaria'
        else:
            estado_venta = 'completa'
            
        margen = precio_promedio - costo_por_kg
        porcentaje_margen = (margen / costo_por_kg) * 100 if costo_por_kg > 0 else 0
        
        if porcentaje_margen < 10:
            rendimiento = 'bajo'
        elif porcentaje_margen < 25:
            rendimiento = 'moderado'
        else:
            rendimiento = 'alto'
            
        # Analizar si el precio está dentro del rango sugerido
        rango_precio = 'noDefinido'
        if min_sugerido is not None and max_sugerido is not None:
            if precio_promedio < min_sugerido:
                rango_precio = 'porDebajoDelRangoSugerido'
            elif precio_promedio > max_sugerido:
                rango_precio = 'porEncimaDelRangoSugerido'
            else:
                rango_precio = 'dentroDelRangoSugerido'
        
        return {
            'estado_venta': estado_venta,
            'rendimiento': rendimiento,
            'rango_precio': rango_precio,
            'recomendacion': self._generar_recomendacion(estado_venta, rendimiento, rango_precio, obj)
        }
        
    def _generar_recomendacion(self, estado_venta, rendimiento, rango_precio, obj):
        """
        Genera una recomendación basada en el análisis de venta.
        """
        if estado_venta == 'completa':
            if rendimiento == 'alto':
                return 'Excelente resultado. Considerar mantener estrategia de precios para futuros lotes similares.'
            elif rendimiento == 'moderado':
                return 'Buen resultado. El lote se vendió completamente con un margen aceptable.'
            else:
                return 'Lote vendido completamente pero con margen bajo. Revisar estrategia de precios o costos.'
        
        elif estado_venta == 'mayoritaria':
            if rango_precio == 'porDebajoDelRangoSugerido':
                return 'Considerar ajustar precio al alza para el stock restante, ya que hay buena demanda incluso con precios bajos.'
            elif rango_precio == 'porEncimaDelRangoSugerido':
                return 'Buen rendimiento con precio alto. Mantener precio para stock restante.'
            else:
                return 'Venta progresando bien. Mantener estrategia actual para el stock restante.'
        
        else:  # parcial
            if rendimiento == 'bajo' or rango_precio == 'porEncimaDelRangoSugerido':
                return 'Considerar reducir precio para acelerar la venta del stock restante.'
            else:
                return 'Revisar estrategia de ventas. El lote no está teniendo la rotación esperada.'

