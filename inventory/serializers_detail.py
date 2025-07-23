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
    
    # Información del producto
    producto_id = serializers.IntegerField(source='producto.id')
    producto_nombre = serializers.CharField(source='producto.nombre')
    marca = serializers.CharField()
    tipo_producto = serializers.SerializerMethodField()
    
    # Información de origen
    proveedor_id = serializers.SerializerMethodField()
    proveedor_nombre = serializers.CharField(source='proveedor')
    procedencia = serializers.CharField()
    pais = serializers.CharField()
    
    # Fechas importantes
    fecha_ingreso = serializers.DateField()
    fecha_maduracion = serializers.DateField()
    
    # Información de peso y cantidad
    cantidad_cajas = serializers.IntegerField()
    box_type_nombre = serializers.CharField(source='box_type.nombre')
    pallet_type_nombre = serializers.SerializerMethodField()
    peso_bruto = serializers.FloatField()
    peso_neto = serializers.FloatField()
    peso_disponible = serializers.SerializerMethodField()
    peso_reservado = serializers.SerializerMethodField()
    peso_vendible = serializers.SerializerMethodField()
    
    # Información de maduración
    estado_maduracion = serializers.CharField()
    ubicacion = serializers.SerializerMethodField()
    
    # Información de costos y precios
    costo_inicial = serializers.FloatField()
    costo_actual = serializers.SerializerMethodField()
    costo_diario_almacenaje = serializers.FloatField()
    precio_recomendado_kg = serializers.SerializerMethodField()
    costo_real_kg = serializers.SerializerMethodField()
    ganancia_kg = serializers.SerializerMethodField()
    margen = serializers.SerializerMethodField()
    
    # Rangos de precios sugeridos
    precio_sugerido_min = serializers.FloatField(allow_null=True)
    precio_sugerido_max = serializers.FloatField(allow_null=True)
    
    # Métricas calculadas
    dias_desde_ingreso = serializers.SerializerMethodField()
    dias_en_bodega = serializers.SerializerMethodField()
    porcentaje_perdida = serializers.SerializerMethodField()
    perdida_estimada = serializers.SerializerMethodField()
    valor_perdida = serializers.SerializerMethodField()
    ingreso_estimado = serializers.SerializerMethodField()
    ganancia_total = serializers.SerializerMethodField()
    
    # Valores de llegada y comparación
    valores_llegada = serializers.SerializerMethodField()
    comparacion_venta = serializers.SerializerMethodField()
    
    # Recomendaciones del sistema
    urgencia_venta = serializers.SerializerMethodField()
    recomendacion = serializers.SerializerMethodField()
    
    # Historial de movimientos y precios
    movimientos = serializers.SerializerMethodField()
    historial_precios = serializers.SerializerMethodField()

    class Meta:
        model = FruitLot
        fields = (
            'id', 'uid', 'codigo', 
            'producto_id', 'producto_nombre', 'marca', 'tipo_producto',
            'proveedor_id', 'proveedor_nombre', 'procedencia', 'pais',
            'fecha_ingreso', 'fecha_maduracion',
            'cantidad_cajas', 'box_type_nombre', 'pallet_type_nombre', 
            'peso_bruto', 'peso_neto', 'peso_disponible', 'peso_reservado', 'peso_vendible',
            'estado_maduracion', 'ubicacion',
            'costo_inicial', 'costo_actual', 'costo_diario_almacenaje', 
            'precio_recomendado_kg', 'costo_real_kg', 'ganancia_kg', 'margen',
            'precio_sugerido_min', 'precio_sugerido_max',
            'dias_desde_ingreso', 'dias_en_bodega', 'porcentaje_perdida', 
            'perdida_estimada', 'valor_perdida', 'ingreso_estimado', 'ganancia_total',
            'valores_llegada', 'comparacion_venta',
            'urgencia_venta', 'recomendacion',
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

    def get_pallet_type_nombre(self, obj):
        if obj.pallet_type:
            return obj.pallet_type.nombre
        return None

    def get_peso_reservado(self, obj):
        from .models import StockReservation
        total = StockReservation.objects.filter(lote=obj).aggregate(total=Sum('cantidad_kg'))['total'] or 0
        return float(total)

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

    def get_costo_actual(self, obj):
        return float(obj.costo_actualizado())

    def get_dias_desde_ingreso(self, obj):
        if obj.fecha_ingreso:
            return (date.today() - obj.fecha_ingreso).days
        return 0

    def get_dias_en_bodega(self, obj):
        return self.get_dias_desde_ingreso(obj)

    def get_porcentaje_perdida(self, obj):
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
        neto = float(obj.peso_neto or 0)
        return round(neto * (self.get_porcentaje_perdida(obj)/100), 2)

    def get_valor_perdida(self, obj):
        perdida = self.get_perdida_estimada(obj)
        costo_actual = float(self.get_costo_actual(obj) or 0)
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
        peso_real = self.get_peso_vendible(obj)
        return round(self.get_precio_recomendado_kg(obj) * peso_real, 2)

    def get_ganancia_total(self, obj):
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
        maduration_history = MadurationHistory.objects.filter(lote=obj).order_by('fecha_cambio')
        
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
        ventas = Sale.objects.filter(lote=obj).order_by('created_at')
        
        for i, venta in enumerate(ventas):
            movimientos.append({
                'id': len(maduration_history) + i + 1,
                'fecha': venta.created_at.isoformat() if hasattr(venta.created_at, 'isoformat') else str(venta.created_at),
                'tipo': 'venta',
                'estado_anterior': None,
                'estado_nuevo': None,
                'cantidad': float(venta.peso_vendido),
                'usuario': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip() if hasattr(venta, 'vendedor') and venta.vendedor else "Sistema",
                'notas': f"Venta #{venta.id} - {venta.cliente.nombre if venta.cliente else getattr(venta, 'nombre_cliente', 'Cliente no especificado')}"
            })
        
        # Obtener otros cambios importantes del historial (simple_history)
        historical_records = obj.history.all().order_by('history_date')
        
        for i, record in enumerate(historical_records):
            # Solo registrar cambios significativos (cantidad_cajas, peso_neto, etc.)
            if i > 0:
                prev_record = historical_records[i-1]
                
                # Cambio en cantidad de cajas
                if record.cantidad_cajas != prev_record.cantidad_cajas:
                    movimientos.append({
                        'id': len(maduration_history) + len(ventas) + i,
                        'fecha': record.history_date.isoformat() if hasattr(record.history_date, 'isoformat') else str(record.history_date),
                        'tipo': 'ajuste_inventario',
                        'estado_anterior': None,
                        'estado_nuevo': None,
                        'cantidad': record.cantidad_cajas - prev_record.cantidad_cajas,
                        'usuario': f"{record.history_user.first_name} {record.history_user.last_name}".strip() if record.history_user else "Sistema",
                        'notas': f"Ajuste de {prev_record.cantidad_cajas} a {record.cantidad_cajas} cajas"
                    })
        
        # Ordenar todos los movimientos por fecha
        return sorted(movimientos, key=lambda x: x['fecha'])

    def get_historial_precios(self, obj):
        """
        Genera un historial de precios basado en los cambios históricos del lote
        y las ventas asociadas.
        """
        historial = []
        
        # Obtener ventas para ver precios aplicados
        ventas = Sale.objects.filter(lote=obj).order_by('created_at')
        
        for i, venta in enumerate(ventas):
            historial.append({
                'id': i + 1,
                'fecha': venta.created_at.isoformat() if hasattr(venta.created_at, 'isoformat') else str(venta.created_at),
                'precio': float(venta.precio_kg),
                'peso_vendido': float(venta.peso_vendido),
                'usuario': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip() if hasattr(venta, 'vendedor') and venta.vendedor else "Sistema",
                'notas': f"Venta #{venta.id} - {venta.cliente.nombre if venta.cliente else getattr(venta, 'nombre_cliente', 'Cliente no especificado')}"
            })
        
        # Si no hay ventas, agregar al menos el precio recomendado actual
        if not historial:
            historial.append({
                'id': 1,
                'fecha': timezone.now().isoformat(),
                'precio': self.get_precio_recomendado_kg(obj),
                'usuario': "Sistema",
                'notas': "Precio recomendado inicial"
            })
        
        return historial
        
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
        
    def get_comparacion_venta(self, obj):
        """
        Compara los valores iniciales del pallet con los valores de venta total.
        """
        # Obtener ventas para calcular totales
        from sales.models import Sale
        ventas = Sale.objects.filter(lote=obj)
        
        # Calcular totales de venta
        peso_total_vendido = sum(float(venta.peso_vendido) for venta in ventas)
        monto_total_ventas = sum(float(venta.peso_vendido * venta.precio_kg) for venta in ventas)
        precio_promedio_kg = round(monto_total_ventas / peso_total_vendido, 2) if peso_total_vendido > 0 else 0
        
        # Calcular valores iniciales
        peso_neto_inicial = float(obj.peso_neto or 0)
        costo_inicial = float(obj.costo_inicial)
        costo_por_kg = round(costo_inicial / peso_neto_inicial, 2) if peso_neto_inicial > 0 else 0
        
        # Calcular diferencias y porcentajes
        diferencia_precio = precio_promedio_kg - costo_por_kg
        porcentaje_margen = round((diferencia_precio / costo_por_kg) * 100, 2) if costo_por_kg > 0 else 0
        porcentaje_vendido = round((peso_total_vendido / peso_neto_inicial) * 100, 2) if peso_neto_inicial > 0 else 0
        
        return {
            'peso_total_vendido': peso_total_vendido,
            'porcentaje_vendido': porcentaje_vendido,
            'monto_total_ventas': monto_total_ventas,
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
            return 'por_debajo'
        elif precio_promedio > max_sugerido:
            return 'por_encima'
        else:
            return 'dentro_rango'
            
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
        rango_precio = 'no_definido'
        if min_sugerido is not None and max_sugerido is not None:
            if precio_promedio < min_sugerido:
                rango_precio = 'por_debajo_del_rango_sugerido'
            elif precio_promedio > max_sugerido:
                rango_precio = 'por_encima_del_rango_sugerido'
            else:
                rango_precio = 'dentro_del_rango_sugerido'
        
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
            if rango_precio == 'por_debajo_del_rango_sugerido':
                return 'Considerar ajustar precio al alza para el stock restante, ya que hay buena demanda incluso con precios bajos.'
            elif rango_precio == 'por_encima_del_rango_sugerido':
                return 'Buen rendimiento con precio alto. Mantener precio para stock restante.'
            else:
                return 'Venta progresando bien. Mantener estrategia actual para el stock restante.'
        
        else:  # parcial
            if rendimiento == 'bajo' or rango_precio == 'por_encima_del_rango_sugerido':
                return 'Considerar reducir precio para acelerar la venta del stock restante.'
            else:
                return 'Revisar estrategia de ventas. El lote no está teniendo la rotación esperada.'

