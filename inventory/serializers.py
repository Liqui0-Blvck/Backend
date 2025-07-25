from rest_framework import serializers
from .models import BoxType, FruitLot, StockReservation, Product, GoodsReception, Supplier, ReceptionDetail
from sales.models import Customer
from django.db.models import Sum

class BoxTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoxType
        fields = ('uid', 'nombre', 'descripcion', 'peso_caja', 'peso_pallet', 'business')

class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    unidad = serializers.CharField(source='get_unidad_display')
    
    class Meta:
        model = Product
        fields = ('uid', 'nombre', 'marca', 'unidad', 'business', 'activo', 'image_path', 'image_url')
    
    def get_image_url(self, obj):
        if obj.image_path and hasattr(obj.image_path, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.image_path.url)
            return obj.image_path.url
        return None


class FruitLotSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.SerializerMethodField()
    box_type_nombre = serializers.SerializerMethodField()
    pallet_type_nombre = serializers.SerializerMethodField()
    costo_actual = serializers.SerializerMethodField()
    peso_reservado = serializers.SerializerMethodField()
    peso_disponible = serializers.SerializerMethodField()
    tipo_producto = serializers.SerializerMethodField()
    dias_desde_ingreso = serializers.SerializerMethodField()
    dias_en_bodega = serializers.SerializerMethodField()
    porcentaje_perdida = serializers.SerializerMethodField()
    perdida_estimada = serializers.SerializerMethodField()
    valor_perdida = serializers.SerializerMethodField()
    # Campo peso_vendible eliminado - usando peso_neto directamente
    precio_recomendado_kg = serializers.SerializerMethodField()
    costo_real_kg = serializers.SerializerMethodField()
    ganancia_kg = serializers.SerializerMethodField()
    margen = serializers.SerializerMethodField()
    ingreso_estimado = serializers.SerializerMethodField()
    ganancia_total = serializers.SerializerMethodField()
    resumen_producto = serializers.SerializerMethodField()
    urgencia_venta = serializers.SerializerMethodField()
    recomendacion = serializers.SerializerMethodField()
    costo_total_pallet = serializers.SerializerMethodField()
    # Campos para información de ventas
    peso_vendido = serializers.SerializerMethodField()
    dinero_generado = serializers.SerializerMethodField()
    porcentaje_vendido = serializers.SerializerMethodField()

    class Meta:
        model = FruitLot
        fields = (
            'uid', 'producto', 'marca', 'proveedor', 'procedencia', 'pais', 'calibre', 'box_type', 'pallet_type',
            'cantidad_cajas', 'peso_bruto', 'peso_neto', 'qr_code', 'business', 'fecha_ingreso',
            'estado_maduracion', 'fecha_maduracion', 'porcentaje_perdida_estimado', 'costo_inicial',
            'costo_diario_almacenaje', 'estado_lote', 'precio_sugerido_min', 'precio_sugerido_max',
            'producto_nombre', 'box_type_nombre', 'pallet_type_nombre', 'costo_actual',
            'peso_reservado', 'peso_disponible', 'tipo_producto', 'dias_desde_ingreso', 'dias_en_bodega',
            'porcentaje_perdida', 'perdida_estimada', 'valor_perdida', 'precio_recomendado_kg',
            'costo_real_kg', 'ganancia_kg', 'margen', 'ingreso_estimado', 'ganancia_total', 'resumen_producto',
            'urgencia_venta', 'recomendacion', 'costo_total_pallet', 'peso_vendido', 'dinero_generado',
            'porcentaje_vendido',
        )

    def get_producto_nombre(self, obj):
        if obj.producto:
            return obj.producto.nombre
        return None

    def get_box_type_nombre(self, obj):
        if obj.box_type:
            return obj.box_type.nombre
        return None

    def get_pallet_type_nombre(self, obj):
        if obj.pallet_type:
            return obj.pallet_type.nombre
        return None

    def get_costo_actual(self, obj):
        return obj.costo_actualizado()

    def get_peso_reservado(self, obj):
        from inventory.models import StockReservation
        total = StockReservation.objects.filter(lote=obj).aggregate(total=Sum('cantidad_kg'))['total'] or 0
        return float(total)

    def get_peso_disponible(self, obj):
        neto = float(obj.peso_neto or 0)
        reservado = self.get_peso_reservado(obj)
        return neto - reservado if neto > reservado else 0

    def get_tipo_producto(self, obj):
        nombre = (obj.producto.nombre if obj.producto else '').lower()
        if 'palta' in nombre or 'aguacate' in nombre:
            return 'palta'
        if 'mango' in nombre:
            return 'mango'
        if 'platano' in nombre or 'plátano' in nombre or 'banano' in nombre:
            return 'platano'
        return 'otro'

    def get_dias_desde_ingreso(self, obj):
        from django.utils import timezone
        if obj.fecha_ingreso:
            return (timezone.now().date() - obj.fecha_ingreso).days
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

    # Método get_peso_vendible eliminado - usando peso_neto o peso_disponible directamente

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
        # Usar peso_disponible en lugar de peso_vendible
        disponible = self.get_peso_disponible(obj)
        perdida = self.get_perdida_estimada(obj)
        peso_real = round(disponible - perdida if disponible > perdida else 0, 2)
        return round(self.get_precio_recomendado_kg(obj) * peso_real, 2)

    def get_ganancia_total(self, obj):
        # Usar peso_disponible en lugar de peso_vendible
        disponible = self.get_peso_disponible(obj)
        perdida = self.get_perdida_estimada(obj)
        peso_real = round(disponible - perdida if disponible > perdida else 0, 2)
        return round(self.get_ganancia_kg(obj) * peso_real, 2)

    def get_resumen_producto(self, obj):
        tipo = self.get_tipo_producto(obj)
        if tipo == 'palta':
            return f"Palta {obj.calibre or 'S/C'} | ${self.get_costo_real_kg(obj):,.0f}/kg | ${self.get_precio_recomendado_kg(obj):,.0f}/kg rec. | {getattr(obj, 'estado_maduracion', '').capitalize()}"
        return None

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

    def get_costo_total_pallet(self, obj):
        # Calcular el costo total multiplicando el costo actual por el peso neto
        return round(float(obj.peso_neto or 0) * float(self.get_costo_actual(obj) or 0), 2)
        
    def get_peso_vendido(self, obj):
        # Importar Sale aquí para evitar importaciones circulares
        from sales.models import Sale
        # Sumar el peso vendido de todas las ventas asociadas a este lote
        total_vendido = Sale.objects.filter(lote=obj).aggregate(total=Sum('peso_vendido'))['total'] or 0
        return float(total_vendido)
    
    def get_dinero_generado(self, obj):
        # Importar Sale aquí para evitar importaciones circulares
        from sales.models import Sale
        # Sumar el total de dinero generado por ventas de este lote
        total_dinero = Sale.objects.filter(lote=obj).aggregate(total=Sum('total'))['total'] or 0
        return float(total_dinero)
    
    def get_porcentaje_vendido(self, obj):
        peso_neto = float(obj.peso_neto or 0)
        if peso_neto > 0:
            peso_vendido = self.get_peso_vendido(obj)
            return round((peso_vendido / peso_neto) * 100, 2)
        return 0

class StockReservationSerializer(serializers.ModelSerializer):
    lote_producto = serializers.SerializerMethodField()
    lote_calibre = serializers.SerializerMethodField()
    usuario_nombre = serializers.SerializerMethodField()
    cliente_nombre = serializers.SerializerMethodField()

    class Meta:
        model = StockReservation
        fields = (
            'uid', 'lote', 'usuario', 'cantidad_kg', 'cantidad_cajas', 'cliente', 'nombre_cliente', 'rut_cliente',
            'telefono_cliente', 'email_cliente', 'estado', 'timeout_minutos', 'business',
            'lote_producto', 'lote_calibre', 'usuario_nombre', 'cliente_nombre',
        )
    
    def get_lote_producto(self, obj):
        if obj.lote and obj.lote.producto:
            return obj.lote.producto.nombre
        return None
    
    def get_lote_calibre(self, obj):
        if obj.lote:
            return obj.lote.calibre
        return None
    
    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return f"{obj.usuario.first_name} {obj.usuario.last_name}".strip() or obj.usuario.username
        return None
    
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        elif obj.nombre_cliente:
            return obj.nombre_cliente
        return None

class ReceptionDetailSerializer(serializers.ModelSerializer):
    recepcion = serializers.SlugRelatedField(queryset=GoodsReception.objects.all(), slug_field='uid')
    producto = serializers.SlugRelatedField(queryset=Product.objects.all(), slug_field='uid')
    producto_nombre = serializers.SerializerMethodField()
    box_type = serializers.SlugRelatedField(queryset=BoxType.objects.all(), slug_field='uid', required=False, allow_null=True)
    def get_producto_nombre(self, obj):
        if obj.producto:
            return obj.producto.nombre
        return None
        
    class Meta:
        model = ReceptionDetail
        fields = (
            'uid', 'recepcion', 'producto', 'producto_nombre', 'variedad', 'calibre', 'box_type', 'numero_pallet', 'cantidad_cajas', 'peso_bruto',
            'peso_tara', 'calidad', 'temperatura', 'estado_maduracion', 'observaciones', 'lote_creado',
            'costo', 'porcentaje_perdida_estimado',
        )

class SupplierRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        from .models import Supplier
        import uuid
        try:
            uuid_obj = uuid.UUID(str(data))
            return Supplier.objects.get(uid=uuid_obj)
        except (ValueError, Supplier.DoesNotExist):
            return super().to_internal_value(data)

class GoodsReceptionSerializer(serializers.ModelSerializer):
    proveedor = SupplierRelatedField(queryset=Supplier.objects.all())
    detalles = ReceptionDetailSerializer(many=True, required=False)
    recibido_por_nombre = serializers.SerializerMethodField()
    revisado_por_nombre = serializers.SerializerMethodField()

    def to_internal_value(self, data):
        import json
        detalles = data.get('detalles')
        if isinstance(detalles, str):
            try:
                data['detalles'] = json.loads(detalles)
            except Exception:
                raise serializers.ValidationError({'detalles': 'Debe ser un JSON válido.'})
        return super().to_internal_value(data)

    class Meta:
        model = GoodsReception
        fields = (
            'uid', 'numero_guia', 'fecha_recepcion', 'proveedor', 'numero_guia_proveedor', 'recibido_por',
            'revisado_por', 'recibido_por_nombre', 'revisado_por_nombre', 'estado', 'observaciones', 
            'total_pallets', 'total_cajas', 'total_peso_bruto', 'business', 'detalles',
        )
        
    def get_recibido_por_nombre(self, obj):
        if obj.recibido_por:
            return f"{obj.recibido_por.first_name} {obj.recibido_por.last_name}".strip()
        return None
        
    def get_revisado_por_nombre(self, obj):
        if obj.revisado_por:
            return f"{obj.revisado_por.first_name} {obj.revisado_por.last_name}".strip()
        return None

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles', [])
        recepcion = GoodsReception.objects.create(**validated_data)
        for detalle_data in detalles_data:
            ReceptionDetail.objects.create(recepcion=recepcion, **detalle_data)
        return recepcion

    def update(self, instance, validated_data):
        detalles_data = validated_data.pop('detalles', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if detalles_data is not None:
            # Elimina los detalles anteriores y crea los nuevos
            instance.detalles.all().delete()
            for detalle_data in detalles_data:
                ReceptionDetail.objects.create(recepcion=instance, **detalle_data)
        return instance

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ('uid', 'nombre', 'rut', 'direccion', 'telefono', 'email', 'contacto', 'observaciones', 'business')
