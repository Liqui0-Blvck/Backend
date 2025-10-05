from rest_framework import serializers
from .models import FruitBin, ReceptionDetail, Product, Supplier, GoodsReception
from .bin_to_lot_models import BinToLotTransformationDetail
from .serializers import ProductSerializer
import uuid
from django.shortcuts import get_object_or_404

class FruitBinListSerializer(serializers.ModelSerializer):
    """Serializador para listar bins de fruta con información resumida"""
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_tipo = serializers.CharField(source='producto.tipo_producto', read_only=True)
    producto = serializers.UUIDField(source='producto.uid', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    proveedor = serializers.UUIDField(source='proveedor.uid', read_only=True)
    propietario_original = serializers.UUIDField(source='propietario_original.uid', read_only=True, allow_null=True)
    propietario_original_nombre = serializers.CharField(source='propietario_original.nombre', read_only=True, allow_null=True)
    recepcion = serializers.UUIDField(source='recepcion.uid', read_only=True, allow_null=True)
    peso_neto = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    calidad_display = serializers.CharField(source='get_calidad_display', read_only=True)
    pago_pendiente = serializers.BooleanField(source='pago_pendiente', read_only=True)
    
    class Meta:
        model = FruitBin
        fields = [
            'uid', 'codigo', 'producto', 'producto_nombre', 'producto_tipo', 'variedad',
            'peso_bruto', 'peso_tara', 'peso_neto', 'costo_por_kilo', 'costo_total', 'estado', 'estado_display',
            'calidad', 'calidad_display', 'proveedor', 'proveedor_nombre', 
            'en_concesion', 'comision_por_kilo', 'comision_base', 'comision_porcentaje', 'comision_monto', 'fecha_limite_concesion',
            'propietario_original', 'propietario_original_nombre',
            'recepcion', 'pago_pendiente', 'fecha_recepcion'
        ]
    
    def get_peso_neto(self, obj):
        return obj.peso_neto


class FruitBinDetailSerializer(serializers.ModelSerializer):
    """Serializador detallado para bins de fruta con toda la información"""
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_tipo = serializers.CharField(source='producto.tipo_producto', read_only=True)
    producto_uid = serializers.UUIDField(source='producto.uid', read_only=True)
    producto_info = ProductSerializer(source='producto', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    proveedor_uid = serializers.UUIDField(source='proveedor.uid', read_only=True, allow_null=True)
    proveedor_info = serializers.SerializerMethodField()
    recepcion_uid = serializers.UUIDField(source='recepcion.uid', read_only=True, allow_null=True)
    propietario_original_uid = serializers.UUIDField(source='propietario_original.uid', read_only=True, allow_null=True)
    propietario_original_nombre = serializers.CharField(source='propietario_original.nombre', read_only=True, allow_null=True)
    peso_neto = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    calidad_display = serializers.CharField(source='get_calidad_display', read_only=True)
    recepcion_info = serializers.SerializerMethodField()
    transformaciones = serializers.SerializerMethodField()
    vendido = serializers.SerializerMethodField()
    venta = serializers.SerializerMethodField()
    pago_pendiente = serializers.SerializerMethodField()
    estado_pago_recepcion = serializers.CharField(source='recepcion.estado_pago', read_only=True)
    
    class Meta:
        model = FruitBin
        fields = [
            'uid', 'codigo', 'producto', 'producto_uid', 'producto_nombre', 'producto_tipo', 'producto_info', 'variedad',
            'peso_bruto', 'peso_tara', 'peso_neto', 'costo_por_kilo', 'costo_total', 'estado', 'estado_display',
            'calidad', 'calidad_display', 'ubicacion', 'recepcion', 'recepcion_uid', 'recepcion_info', 'fecha_recepcion',
            'proveedor', 'proveedor_uid', 'proveedor_nombre', 'proveedor_info',
            'en_concesion', 'comision_por_kilo', 'comision_base', 'comision_porcentaje', 'comision_monto', 'fecha_limite_concesion',
            'propietario_original_uid', 'propietario_original_nombre',
            'pago_pendiente', 'temperatura', 'observaciones',
            'created_at', 'updated_at', 'vendido', 'venta', 'transformaciones'
        ]
    
    def get_peso_neto(self, obj):
        return obj.peso_neto
    
    def get_proveedor_info(self, obj):
        """Retorna información básica del proveedor"""
        if obj.proveedor:
            return {
                'uid': obj.proveedor.uid,
                'nombre': obj.proveedor.nombre,
                'rut': obj.proveedor.rut,
                'telefono': obj.proveedor.telefono,
                'email': obj.proveedor.email
            }
        return None
    
    def get_recepcion_info(self, obj):
        """Retorna información básica de la recepción"""
        if obj.recepcion:
            return {
                'uid': obj.recepcion.uid,
                'numero_guia': obj.recepcion.numero_guia,
                'fecha_recepcion': obj.recepcion.fecha_recepcion
            }
        return None

    def get_transformaciones(self, obj):
        """Devuelve un resumen de transformaciones Bin -> Lote (pallet) para trazabilidad."""
        try:
            detalles = (
                BinToLotTransformationDetail.objects
                .select_related('transformacion', 'bin', 'transformacion__lote')
                .filter(bin=obj)
                .order_by('-transformacion__fecha_transformacion')[:5]
            )
            data = []
            for d in detalles:
                t = d.transformacion
                data.append({
                    'transformacion_uid': getattr(t, 'uid', None),
                    'fecha_transformacion': getattr(t, 'fecha_transformacion', None),
                    'lote_uid': getattr(getattr(t, 'lote', None), 'uid', None),
                    'kg_descontados': d.kg_descontados,
                    'peso_bruto_previo': d.peso_bruto_previo,
                    'peso_tara_previa': d.peso_tara_previa,
                })
            return data
        except Exception:
            return []

    def get_vendido(self, obj):
        """Retorna True si el bin está vendido, basado en su estado."""
        return obj.estado == 'VENDIDO'

    def get_venta(self, obj):
        """Si el bin fue vendido, retorna información de la venta asociada más reciente."""
        # Solo intentar si está marcado como vendido o si hay relación
        try:
            from sales.models import SaleItem
            si = (
                SaleItem.objects
                .select_related('venta', 'venta__cliente', 'venta__vendedor')
                .filter(bin=obj)
                .order_by('-created_at')
                .first()
            )
            if not si or not si.venta:
                return None
            venta = si.venta
            data = {
                'venta_uid': getattr(venta, 'uid', None),
                'codigo_venta': getattr(venta, 'codigo_venta', None),
                'fecha': getattr(venta, 'created_at', None),
                'total': getattr(venta, 'total', None),
                'metodo_pago': getattr(venta, 'metodo_pago', None),
                'estado_pago': getattr(venta, 'estado_pago', None),
                'cancelada': getattr(venta, 'cancelada', None),
                'cliente': None,
                'vendedor': None,
                'item': {
                    'peso_vendido': getattr(si, 'peso_vendido', None),
                    'unidades_vendidas': getattr(si, 'unidades_vendidas', None),
                    'subtotal': getattr(si, 'subtotal', None),
                    'uid': getattr(si, 'uid', None),
                }
            }
            cliente = getattr(venta, 'cliente', None)
            if cliente:
                data['cliente'] = {
                    'uid': getattr(cliente, 'uid', None),
                    'nombre': getattr(cliente, 'nombre', None),
                    'rut': getattr(cliente, 'rut', None),
                    'telefono': getattr(cliente, 'telefono', None),
                }
            vendedor = getattr(venta, 'vendedor', None)
            if vendedor:
                data['vendedor'] = {
                    'uid': getattr(vendedor, 'uid', None),
                    'nombre': getattr(vendedor, 'full_name', None) or getattr(vendedor, 'username', None),
                }
            return data
        except Exception:
            return None
    
    def get_pago_pendiente(self, obj):
        try:
            if obj.recepcion and getattr(obj.recepcion, 'estado_pago', None):
                return obj.recepcion.estado_pago == 'pendiente'
        except Exception:
            pass
        return False


class FruitBinBulkCreateSerializer(serializers.Serializer):
    """Serializador para la creación masiva de bins de fruta"""
    cantidad = serializers.IntegerField(min_value=1, required=True, help_text='Cantidad de bins a crear')
    producto = serializers.UUIDField(required=True, help_text='ID del producto')
    variedad = serializers.CharField(required=False, allow_blank=True, help_text='Variedad de la fruta')
    peso_bruto = serializers.DecimalField(max_digits=10, decimal_places=2, required=True, help_text='Peso bruto en kg')
    peso_tara = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, help_text='Peso de la tara en kg')
    costo_por_kilo = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, help_text='Costo por kilo del bin')
    costo_total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, help_text='Costo total del bin')
    estado = serializers.ChoiceField(choices=FruitBin.ESTADO_CHOICES, default='DISPONIBLE', help_text='Estado del bin')
    calidad = serializers.ChoiceField(choices=FruitBin.CALIDAD_CHOICES, default='3RA', help_text='Calibraje/calidad del bin')
    proveedor = serializers.UUIDField(required=False, allow_null=True, help_text='ID del proveedor')
    recepcion = serializers.UUIDField(required=False, allow_null=True, help_text='ID de la recepción')
    fecha_recepcion = serializers.DateField(required=False, help_text='Fecha de recepción')
    temperatura = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True, help_text='Temperatura de la fruta')
    observaciones = serializers.CharField(required=False, allow_blank=True, help_text='Observaciones adicionales')
    # Concesión
    en_concesion = serializers.BooleanField(required=False, default=False, help_text='Indica si el bin está en concesión')
    comision_por_kilo = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, help_text='Comisión por kilo para bin en concesión')
    fecha_limite_concesion = serializers.DateField(required=False, allow_null=True, help_text='Fecha límite para vender el bin en concesión')
    propietario_original = serializers.UUIDField(required=False, allow_null=True, help_text='UID del proveedor propietario original')
    # Entrada flexible de comisión (como GoodsReception)
    comision_base = serializers.CharField(required=False, allow_blank=True, help_text="Base de comisión: 'kg' | 'caja' | 'unidad' | 'venta'")
    comision_monto = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, help_text='Monto directo de comisión según la base')
    comision_porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True, help_text='Porcentaje de comisión (0-100)')
    # Pago proveedor
    pago_pendiente = serializers.BooleanField(required=False, default=False, help_text='Indica si el pago al proveedor de este bin está pendiente')
    
    def _normalize_calidad(self, valor):
        """Acepta enteros o strings y retorna una clave válida de FruitBin.CALIDAD_CHOICES.
        Mapeo propuesto:
        0/"DESCARTE" -> 'DESCARTE'
        1 -> '5TA', 2 -> '4TA', 3 -> '3RA', 4 -> '2DA', 5 -> '1RA', 6 -> 'EXTRA', 7 -> 'SUPER_EXTRA'
        Si ya viene una clave válida, se respeta.
        """
        if valor is None:
            return '3RA'
        # Si viene como número o string de número
        try:
            num = int(valor)
            if num <= 0:
                return 'DESCARTE'
            mapa = {
                1: '5TA',
                2: '4TA',
                3: '3RA',
                4: '2DA',
                5: '1RA',
                6: 'EXTRA',
                7: 'SUPER_EXTRA',
            }
            return mapa.get(num, '3RA')
        except (ValueError, TypeError):
            pass
        # Strings
        s = str(valor).strip().upper()
        # Normalizar nombres comunes
        alias = {
            'DESCARTE': 'DESCARTE',
            'DESCARTADO': 'DESCARTE',
            '5TA': '5TA', 'QUINTA': '5TA',
            '4TA': '4TA', 'CUARTA': '4TA',
            '3RA': '3RA', 'TERCERA': '3RA',
            '2DA': '2DA', 'SEGUNDA': '2DA',
            '1RA': '1RA', 'PRIMERA': '1RA',
            'EXTRA': 'EXTRA',
            'SUPER EXTRA': 'SUPER_EXTRA', 'SUPER_EXTRA': 'SUPER_EXTRA',
        }
        return alias.get(s, '3RA')

    def create(self, validated_data):
        """Crea múltiples bins con los mismos datos"""
        cantidad = validated_data.pop('cantidad')
        business = validated_data.pop('business', None)
        # Extraer inputs flexibles de comisión
        en_concesion = validated_data.get('en_concesion', False)
        comision_base = validated_data.pop('comision_base', None)
        comision_monto = validated_data.pop('comision_monto', None)
        comision_porcentaje = validated_data.pop('comision_porcentaje', None)
        # Normalizar calidad (acepta numérico o string)
        if 'calidad' in validated_data:
            validated_data['calidad'] = self._normalize_calidad(validated_data.get('calidad'))
        
        # Convertir UUIDs a instancias de modelos
        producto_uuid = validated_data.pop('producto')
        producto = get_object_or_404(Product, uid=producto_uuid)
        
        # Manejar el proveedor (opcional)
        proveedor = None
        if 'proveedor' in validated_data and validated_data['proveedor']:
            proveedor_uuid = validated_data.pop('proveedor')
            proveedor = get_object_or_404(Supplier, uid=proveedor_uuid)
        
        # Manejar propietario_original (opcional)
        propietario_original = None
        if 'propietario_original' in validated_data and validated_data['propietario_original']:
            propietario_uuid = validated_data.pop('propietario_original')
            propietario_original = get_object_or_404(Supplier, uid=propietario_uuid)

        # Manejar la recepción (opcional)
        recepcion = None
        if 'recepcion' in validated_data and validated_data['recepcion']:
            recepcion_uuid = validated_data.pop('recepcion')
            recepcion = get_object_or_404(GoodsReception, uid=recepcion_uuid)
        
        bins_creados = []
        for i in range(cantidad):
            # Generar un código único para cada bin
            codigo = f"BIN-{uuid.uuid4().hex[:8].upper()}"
            
            # Crear el bin
            bin_data = {
                'codigo': codigo,
                'business': business,
                'producto': producto,
                'proveedor': proveedor,
                'propietario_original': propietario_original,
                'recepcion': recepcion,
                **validated_data
            }
            # Persistir configuración de comisión tal como vino
            bin_data['comision_base'] = comision_base
            bin_data['comision_monto'] = comision_monto
            bin_data['comision_porcentaje'] = comision_porcentaje
            # Persistir estado de pago si vino
            if 'pago_pendiente' in validated_data:
                bin_data['pago_pendiente'] = validated_data['pago_pendiente']
            # Calcular costo_total si no viene y hay costo_por_kilo
            try:
                if bin_data.get('costo_total') in (None, '') and bin_data.get('costo_por_kilo') not in (None, ''):
                    from decimal import Decimal as D
                    peso_bruto = D(str(bin_data.get('peso_bruto') or 0))
                    peso_tara = D(str(bin_data.get('peso_tara') or 0))
                    peso_neto_est = max(peso_bruto - peso_tara, D('0'))
                    bin_data['costo_total'] = (D(str(bin_data['costo_por_kilo'])) * peso_neto_est).quantize(D('0.01'))
            except Exception:
                pass
            # Resolver comisión por kilo si corresponde (solo base 'kg')
            try:
                from decimal import Decimal as D
                if en_concesion and (comision_base == 'kg'):
                    if comision_monto not in (None, ''):
                        bin_data['comision_por_kilo'] = D(str(comision_monto))
                    elif comision_porcentaje not in (None, ''):
                        costo_kg = bin_data.get('costo_por_kilo')
                        if costo_kg not in (None, ''):
                            bin_data['comision_por_kilo'] = D(str(costo_kg)) * D(str(comision_porcentaje)) / D('100')
            except Exception:
                pass
            
            bin_obj = FruitBin.objects.create(**bin_data)
            bins_creados.append(bin_obj)
        
        return bins_creados
