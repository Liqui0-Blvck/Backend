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
    estadoAnterior = serializers.CharField(allow_null=True)
    estadoNuevo = serializers.CharField(allow_null=True)
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
    valoresLlegada = serializers.SerializerMethodField()
    comparacionVenta = serializers.SerializerMethodField()
    
    # Recomendaciones del sistema
    recomendaciones = serializers.SerializerMethodField()
    
    # Historial de movimientos y precios
    movimientos = serializers.SerializerMethodField()
    historialPrecios = serializers.SerializerMethodField()
    
    def get_producto(self, obj):
        return {
            'id': obj.producto.id if obj.producto else None,
            'nombre': obj.producto.nombre if obj.producto else None,
            'marca': obj.marca,
            'tipo': self.get_tipoProducto(obj)
        }
    
    def get_origen(self, obj):
        return {
            'proveedorId': self.get_proveedorId(obj),
            'proveedor': obj.proveedor,
            'procedencia': obj.procedencia,
            'pais': obj.pais
        }
    
    def get_fechas(self, obj):
        return {
            'recepcion': obj.fecha_ingreso,
            'maduracion': obj.fecha_maduracion,
            'diasEnInventario': self.get_diasEnInventario(obj),
            'diasDesdeIngreso': self.get_diasDesdeIngreso(obj),
            'diasEnBodega': self.get_diasEnBodega(obj)
        }
    
    def get_inventario(self, obj):
        return {
            'cantidadCajasInicial': obj.cantidad_cajas,
            'cantidadCajasActual': self.get_cantidadCajasActual(obj),
            'boxType': obj.box_type.nombre if obj.box_type else None,
            'palletType': self.get_palletType(obj),
            'pesoBruto': obj.peso_bruto,
            'pesoNeto': obj.peso_neto,
            'cantidadInicialKg': self.get_cantidadInicialKg(obj),
            'cantidadActualKg': self.get_cantidadActualKg(obj),
            'pesoDisponible': self.get_pesoDisponible(obj),
            'pesoReservado': self.get_pesoReservado(obj),
            'pesoVendible': self.get_pesoVendible(obj),
            'valorInventario': self.get_valorInventario(obj)
        }
    
    def get_maduracion(self, obj):
        return {
            'estado': obj.estado_maduracion,
            'ubicacion': self.get_ubicacion(obj)
        }
    
    def get_precios(self, obj):
        return {
            'precioCompra': obj.costo_inicial,
            'precioActual': self.get_precioActual(obj),
            'costoDiarioAlmacenaje': obj.costo_diario_almacenaje,
            'precioRecomendadoKg': self.get_precioRecomendadoKg(obj),
            'costoRealKg': self.get_costoRealKg(obj),
            'gananciaKg': self.get_gananciaKg(obj),
            'margen': self.get_margen(obj),
            'precioSugeridoMin': obj.precio_sugerido_min,
            'precioSugeridoMax': obj.precio_sugerido_max
        }
    
    def get_metricas(self, obj):
        return {
            'porcentajePerdida': self.get_porcentajePerdida(obj),
            'perdidaEstimada': self.get_perdidaEstimada(obj),
            'valorPerdida': self.get_valorPerdida(obj),
            'ingresoEstimado': self.get_ingresoEstimado(obj),
            'gananciaTotal': self.get_gananciaTotal(obj)
        }
    
    def get_recomendaciones(self, obj):
        return {
            'urgenciaVenta': self.get_urgenciaVenta(obj),
            'recomendacion': self.get_recomendacion(obj)
        }

    # Los campos ahora están agrupados en objetos anidados
    
    class Meta:
        model = FruitLot
        fields = (
            'id', 'uid', 'codigo',
            'producto', 'origen', 'fechas', 'inventario', 'maduracion',
            'precios', 'metricas', 'recomendaciones',
            'valoresLlegada', 'comparacionVenta',
            'movimientos', 'historialPrecios',
        )

    def get_tipoProducto(self, obj):
        nombre = (obj.producto.nombre if obj.producto else '').lower()
        if 'palta' in nombre or 'aguacate' in nombre:
            return 'palta'
        if 'mango' in nombre:
            return 'mango'
        if 'platano' in nombre or 'plátano' in nombre or 'banano' in nombre:
            return 'platano'
        return 'otro'

    def get_proveedorId(self, obj):
        # En este caso, proveedor es un string, no un objeto relacionado
        # Devolvemos None o un ID ficticio según sea necesario
        return None

    def get_palletType(self, obj):
        if obj.pallet_type:
            return obj.pallet_type.nombre
        return None
        
    def get_cantidadCajasActual(self, obj):
        # Por defecto devolvemos la cantidad inicial de cajas
        # Este método podría ser modificado para calcular la cantidad actual
        # basado en ventas u otros movimientos
        return obj.cantidad_cajas
        
    def get_cantidadInicialKg(self, obj):
        tipo = self.get_tipoProducto(obj)
        if tipo == 'palta':
            return float(obj.peso_neto or 0)
        return None
        
    def get_cantidadActualKg(self, obj):
        tipo = self.get_tipoProducto(obj)
        if tipo == 'palta':
            return float(self.get_pesoDisponible(obj))
        return None

    def get_pesoReservado(self, obj):
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

    def get_pesoDisponible(self, obj):
        neto = float(obj.peso_neto or 0)
        reservado = self.get_pesoReservado(obj)
        return neto - reservado if neto > reservado else 0

    def get_pesoVendible(self, obj):
        disponible = self.get_pesoDisponible(obj)
        perdida = self.get_perdidaEstimada(obj)
        return disponible - perdida if disponible > perdida else 0

    def get_ubicacion(self, obj):
        # Este campo no existe en el modelo original, se podría implementar
        # según la lógica de negocio o devolver un valor por defecto
        return "Bodega principal"

    def get_precioActual(self, obj):
        return float(obj.costo_actualizado())

    def get_diasEnInventario(self, obj):
        if obj.fecha_ingreso:
            return (date.today() - obj.fecha_ingreso).days
        return 0

    def get_diasDesdeIngreso(self, obj):
        if obj.fecha_ingreso:
            return (date.today() - obj.fecha_ingreso).days
        return 0

    def get_diasEnBodega(self, obj):
        return self.get_diasDesdeIngreso(obj)
        
    def get_valorInventario(self, obj):
        tipo = self.get_tipoProducto(obj)
        if tipo == 'palta':
            # Para paltas: kilos netos * precio_actual
            return float(obj.peso_neto or 0) * float(self.get_precioActual(obj))
        else:
            # Para otros: cantidad de cajas * precio_inicial
            return float(obj.cantidad_cajas or 0) * float(obj.costo_inicial or 0)

    def get_porcentajePerdida(self, obj):
        """
        Calcula el porcentaje de pérdida basado en el tipo de producto y estado de maduración
        """
        tipo = self.get_tipoProducto(obj)
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

    def get_perdidaEstimada(self, obj):
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
                porcentaje = self.get_porcentajePerdida(obj)
                return round(peso_inicial * (porcentaje/100), 2)
        except Exception:
            pass
            
        # Si no hay historial, usamos el método anterior como fallback
        neto = float(obj.peso_neto or 0)
        return round(neto * (self.get_porcentajePerdida(obj)/100), 2)

    def get_valorPerdida(self, obj):
        """
        Calcula el valor de la pérdida basado en los valores iniciales del historial
        """
        try:
            # Obtenemos el primer registro del historial
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                
                # Obtenemos la pérdida estimada y el costo inicial
                perdida = self.get_perdidaEstimada(obj)
                costo_inicial = float(getattr(primer_registro, 'costo_inicial', 0) or 0)
                
                return round(perdida * costo_inicial, 2)
        except Exception:
            pass
            
        # Si no hay historial, usamos el método anterior como fallback
        perdida = self.get_perdidaEstimada(obj)
        costo_actual = float(self.get_precioActual(obj) or 0)
        return round(perdida * costo_actual, 2)

    def get_precioRecomendadoKg(self, obj):
        costo_real = self.get_costoRealKg(obj)
        return round(costo_real * 1.3, 2)

    def get_costoRealKg(self, obj):
        return float(obj.costo_inicial or 0)

    def get_gananciaKg(self, obj):
        return round(self.get_precioRecomendadoKg(obj) - self.get_costoRealKg(obj), 2)

    def get_margen(self, obj):
        costo = self.get_costoRealKg(obj)
        if costo > 0:
            return round((self.get_gananciaKg(obj) / costo) * 100, 2)
        return 25.0

    def get_ingresoEstimado(self, obj):
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
        peso_real = self.get_pesoVendible(obj)
        return round(self.get_precioRecomendadoKg(obj) * peso_real, 2)

    def get_gananciaTotal(self, obj):
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
        peso_real = self.get_pesoVendible(obj)
        return round(self.get_gananciaKg(obj) * peso_real, 2)

    def get_urgenciaVenta(self, obj):
        estado = getattr(obj, 'estado_maduracion', 'verde')
        if estado == 'maduro':
            return 'alta'
        if estado == 'sobremaduro':
            return 'critica'
        return 'baja'

    def get_recomendacion(self, obj):
        estado = getattr(obj, 'estado_maduracion', 'verde')
        precio = self.get_precioRecomendadoKg(obj)
        if estado == 'verde':
            return {
                'accion': 'esperar',
                'mensaje': 'Mantener en cámara de maduración controlada. Revisar en 3 días.',
                'precioSugerido': precio
            }
        elif estado == 'pre-maduro':
            return {
                'accion': 'prepararVenta',
                'mensaje': 'Preparar para venta en 2 días.',
                'precioSugerido': precio
            }
        elif estado == 'maduro':
            return {
                'accion': 'vender',
                'mensaje': 'Vender lo antes posible.',
                'precioSugerido': precio
            }
        elif estado == 'sobremaduro':
            return {
                'accion': 'liquidar',
                'mensaje': 'Liquidar stock urgentemente.',
                'precioSugerido': precio
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
            estadoAnterior = None
            if i > 0:
                estadoAnterior = maduration_history[i-1].estado_maduracion
                
            movimientos.append({
                'id': i + 1,
                'fecha': history.fecha_cambio.isoformat() if hasattr(history.fecha_cambio, 'isoformat') else str(history.fecha_cambio),
                'tipo': 'cambioMaduracion',
                'estadoAnterior': estadoAnterior,
                'estadoNuevo': history.estado_maduracion,
                'cantidad': None,
                'usuario': 'Sistema',  # Podría mejorarse si se guarda el usuario que hizo el cambio
                'notas': None
            })
        
        # Obtener historial de ventas
        ventas = Sale.objects.filter(items__lote=obj).distinct()        
        for i, venta in enumerate(ventas):
            # Obtener el peso vendido desde los items de la venta
            pesoVendido = venta.items.filter(lote=obj).aggregate(total=Sum('peso_vendido'))['total'] or 0
            
            # Añadir la venta como un movimiento
            movimientos.append({
                'id': len(maduration_history) + i + 1,
                'fecha': venta.created_at.isoformat() if hasattr(venta.created_at, 'isoformat') else str(venta.created_at),
                'tipo': 'venta',
                'estadoAnterior': None,
                'estadoNuevo': None,
                'cantidad': pesoVendido,
                'usuario': f"{venta.vendedor.first_name} {venta.vendedor.last_name}".strip() if hasattr(venta, 'vendedor') and venta.vendedor else "Sistema",
                'notas': f"Venta #{venta.id} - {venta.cliente.nombre if venta.cliente else getattr(venta, 'nombre_cliente', 'Cliente no especificado')}"
            })
            
        # Ordenar movimientos por fecha
        movimientos = sorted(movimientos, key=lambda x: x['fecha'])
        
        # Renumerar IDs después de ordenar
        for i, mov in enumerate(movimientos):
            mov['id'] = i + 1
            
        return movimientos
        
    def get_valoresLlegada(self, obj):
        """
        Obtiene los valores iniciales del pallet al momento de su llegada desde el historial.
        """
        # Obtener el primer registro histórico (el más antiguo)
        historicos = obj.history.all().order_by('history_date')
        primer_registro = historicos.first() if historicos.exists() else None
        
        if primer_registro:
            # Usar valores del primer registro histórico
            return {
                'fechaIngreso': primer_registro.fecha_ingreso.isoformat() if hasattr(primer_registro.fecha_ingreso, 'isoformat') else str(primer_registro.fecha_ingreso),
                'pesoBrutoInicial': float(primer_registro.peso_bruto if primer_registro.peso_bruto else 0),
                'pesoNetoInicial': float(primer_registro.peso_neto if primer_registro.peso_neto else 0),
                'cantidadCajasInicial': primer_registro.cantidad_cajas,
                'costoInicial': float(primer_registro.costo_inicial if primer_registro.costo_inicial else 0),
                'costoPorKgInicial': round(float(primer_registro.costo_inicial) / float(primer_registro.peso_neto), 2) 
                                        if primer_registro.peso_neto and float(primer_registro.peso_neto) > 0 else 0,
                'precioSugeridoMin': float(primer_registro.precio_sugerido_min) if primer_registro.precio_sugerido_min else None,
                'precioSugeridoMax': float(primer_registro.precio_sugerido_max) if primer_registro.precio_sugerido_max else None
            }
        else:
            # Fallback a los valores actuales si no hay historial
            return {
                'fechaIngreso': obj.fecha_ingreso.isoformat() if hasattr(obj.fecha_ingreso, 'isoformat') else str(obj.fecha_ingreso),
                'pesoBrutoInicial': float(obj.peso_bruto if obj.peso_bruto else 0),
                'pesoNetoInicial': float(obj.peso_neto or 0),
                'cantidadCajasInicial': obj.cantidad_cajas,
                'costoInicial': float(obj.costo_inicial if obj.costo_inicial else 0),
                'costoPorKgInicial': round(float(obj.costo_inicial) / float(obj.peso_neto), 2) if obj.peso_neto and float(obj.peso_neto) > 0 else 0,
                'precioSugeridoMin': float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None,
                'precioSugeridoMax': float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None
            }
    
    def get_historialPrecios(self, obj):
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
                'pesoVendido': float(item.peso_vendido) if item.peso_vendido else 0,
                'usuario': f"{item.venta.vendedor.first_name} {item.venta.vendedor.last_name}".strip() if hasattr(item.venta, 'vendedor') and item.venta.vendedor else "Sistema",
                'notas': f"Venta #{item.venta.id} - {item.venta.cliente.nombre if item.venta.cliente else getattr(item.venta, 'nombre_cliente', 'Cliente no especificado')}"
            })
        
        # Si no hay ventas, agregar al menos el precio recomendado actual
        if not historial:
            historial.append({
                'id': 1,
                'fecha': timezone.now().isoformat(),
                'precio': self.get_precioRecomendadoKg(obj),
                'pesoVendido': 0,
                'usuario': "Sistema",
                'notas': "Precio recomendado inicial"
            })
        
        return historial
        
    def get_comparacionVenta(self, obj):
        """
        Compara los valores iniciales del pallet con los valores de venta total.
        """
        # Obtener ventas para calcular totales
        from sales.models import Sale
        ventas = Sale.objects.filter(items__lote=obj).distinct()
        
        # Calcular totales de venta con redondeo adecuado
        from sales.models import SaleItem
        items_lote = SaleItem.objects.filter(lote=obj)
        pesoTotalVendido = round(sum(float(item.peso_vendido) for item in items_lote), 2)
        montoTotalVentas = round(sum(float(item.subtotal) for item in items_lote), 2)
        precioPromedioKg = round(montoTotalVentas / pesoTotalVendido, 2) if pesoTotalVendido > 0 else 0
        
        # Obtener valores iniciales del historial
        try:
            historial = obj.history.all().order_by('history_date')
            if historial.exists():
                primer_registro = historial.first()
                pesoNetoInicial = float(getattr(primer_registro, 'peso_neto', 0) or 0)
                costoInicial = float(getattr(primer_registro, 'costo_inicial', 0) or 0)
            else:
                # Fallback a valores actuales
                pesoNetoInicial = float(obj.peso_neto or 0)
                costoInicial = float(obj.costo_inicial or 0)
        except Exception:
            # Fallback a valores actuales en caso de error
            pesoNetoInicial = float(obj.peso_neto or 0)
            costoInicial = float(obj.costo_inicial or 0)
        
        # Evitar división por cero
        if pesoNetoInicial <= 0:
            pesoNetoInicial = 1  # Valor mínimo para evitar división por cero
        
        # Calcular costo por kg con validación
        costoPorKg = round(costoInicial / pesoNetoInicial, 2) if pesoNetoInicial > 0 else 0
        
        # Calcular diferencias y porcentajes con límites razonables
        diferenciaPrecio = round(precioPromedioKg - costoPorKg, 2)
        
        # Calcular porcentaje de margen con límites razonables
        if costoPorKg > 0:
            porcentajeMargen = round((diferenciaPrecio / costoPorKg) * 100, 2)
            # Limitar a un rango razonable para presentación (-100% a 1000%)
            porcentajeMargen = max(min(porcentajeMargen, 1000), -100)
        else:
            porcentajeMargen = 0
        
        # Calcular porcentaje vendido con límites razonables
        porcentajeVendido = round((pesoTotalVendido / pesoNetoInicial) * 100, 2)
        # Limitar a un máximo de 100% para presentación normal
        porcentajeVendido = min(porcentajeVendido, 100)
        
        # Calcular ganancia total de ventas reales (monto total de ventas - costo total del pallet)
        costoTotalPallet = float(round(obj.costo_actualizado() * obj.peso_neto, 2))  # Costo total inicial del pallet
        gananciaTotalVentas = round(float(montoTotalVentas) - costoTotalPallet, 2)
        
        return {
            'pesoTotalVendido': pesoTotalVendido,
            'porcentajeVendido': porcentajeVendido,
            'montoTotalVentas': montoTotalVentas,
            'gananciaTotalVentas': gananciaTotalVentas,
            'precioPromedioKg': precioPromedioKg,
            'costoPorKg': costoPorKg,
            'diferenciaPrecio': diferenciaPrecio,
            'porcentajeMargen': porcentajeMargen,
            'rentabilidad': 'positiva' if diferenciaPrecio > 0 else 'negativa' if diferenciaPrecio < 0 else 'neutra',
            'precioDentroRango': self._precioDentroRango(precioPromedioKg, obj),
            'analisis': self._generarAnalisisVenta(precioPromedioKg, costoPorKg, porcentajeVendido, obj)
        }
        
    def _precioDentroRango(self, precioPromedio, obj):
        """
        Determina si el precio promedio está dentro del rango sugerido.
        """
        minSugerido = float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None
        maxSugerido = float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None
        
        if minSugerido is None or maxSugerido is None:
            return None
            
        if precioPromedio < minSugerido:
            return 'porDebajo'
        elif precioPromedio > maxSugerido:
            return 'porEncima'
        else:
            return 'dentroRango'
            
    def _generarAnalisisVenta(self, precioPromedio, costoPorKg, porcentajeVendido, obj):
        """
        Genera un análisis de la venta basado en precios y porcentaje vendido.
        """
        minSugerido = float(obj.precio_sugerido_min) if obj.precio_sugerido_min else None
        maxSugerido = float(obj.precio_sugerido_max) if obj.precio_sugerido_max else None
        
        if porcentajeVendido < 50:
            estadoVenta = 'parcial'
        elif porcentajeVendido < 90:
            estadoVenta = 'mayoritaria'
        else:
            estadoVenta = 'completa'
            
        margen = precioPromedio - costoPorKg
        porcentajeMargen = (margen / costoPorKg) * 100 if costoPorKg > 0 else 0
        
        if porcentajeMargen < 10:
            rendimiento = 'bajo'
        elif porcentajeMargen < 25:
            rendimiento = 'moderado'
        else:
            rendimiento = 'alto'
            
        # Analizar si el precio está dentro del rango sugerido
        rangoPrecio = 'noDefinido'
        if minSugerido is not None and maxSugerido is not None:
            if precioPromedio < minSugerido:
                rangoPrecio = 'porDebajoDelRangoSugerido'
            elif precioPromedio > maxSugerido:
                rangoPrecio = 'porEncimaDelRangoSugerido'
            else:
                rangoPrecio = 'dentroDelRangoSugerido'
        
        return {
            'estadoVenta': estadoVenta,
            'rendimiento': rendimiento,
            'rangoPrecio': rangoPrecio,
            'recomendacion': self._generarRecomendacion(estadoVenta, rendimiento, rangoPrecio, obj)
        }
        
    def _generarRecomendacion(self, estadoVenta, rendimiento, rangoPrecio, obj):
        """
        Genera una recomendación basada en el análisis de venta.
        """
        if estadoVenta == 'completa':
            if rendimiento == 'alto':
                return 'Excelente resultado. Considerar mantener estrategia de precios para futuros lotes similares.'
            elif rendimiento == 'moderado':
                return 'Buen resultado. El lote se vendió completamente con un margen aceptable.'
            else:
                return 'Lote vendido completamente pero con margen bajo. Revisar estrategia de precios o costos.'
        
        elif estadoVenta == 'mayoritaria':
            if rangoPrecio == 'porDebajoDelRangoSugerido':
                return 'Considerar ajustar precio al alza para el stock restante, ya que hay buena demanda incluso con precios bajos.'
            elif rangoPrecio == 'porEncimaDelRangoSugerido':
                return 'Buen rendimiento con precio alto. Mantener precio para stock restante.'
            else:
                return 'Venta progresando bien. Mantener estrategia actual para el stock restante.'
        
        else:  # parcial
            if rendimiento == 'bajo' or rangoPrecio == 'porEncimaDelRangoSugerido':
                return 'Considerar reducir precio para acelerar la venta del stock restante.'
            else:
                return 'Revisar estrategia de ventas. El lote no está teniendo la rotación esperada.'

