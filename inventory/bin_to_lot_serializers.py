from rest_framework import serializers
from .models import FruitBin, FruitLot, BoxType, PalletType
from .bin_to_lot_models import BinToLotTransformation, BinToLotTransformationDetail
from django.db import transaction
from django.utils import timezone

class BinToLotSerializer(serializers.Serializer):
    """
    Serializador para transformar bins de fruta a lotes (pallets)
    """
    bin_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="Lista de IDs de bins a transformar"
    )
    box_type_id = serializers.UUIDField(
        help_text="ID del tipo de caja a utilizar en el lote"
    )
    cantidad_cajas = serializers.IntegerField(
        help_text="Cantidad de cajas en el nuevo lote"
    )
    proveedor = serializers.UUIDField(
        required=False,
        help_text="UUID del proveedor (opcional). Si no se proporciona, se usará el proveedor del bin"
    )
    calibre = serializers.CharField(
        max_length=16,
        help_text="Calibre del nuevo lote"
    )
    estado_maduracion = serializers.ChoiceField(
        choices=[('verde','Verde'),('pre-maduro','Pre-maduro'),('maduro','Maduro'),('sobremaduro','Sobremaduro')],
        default='verde',
        help_text="Estado de maduración inicial del lote"
    )
    costo_inicial = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo inicial por kg del nuevo lote"
    )
    precio_sugerido_min = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Precio mínimo sugerido por kg o unidad"
    )
    precio_sugerido_max = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Precio máximo sugerido por kg o unidad"
    )

    def validate(self, data):
        """
        Validaciones adicionales para la transformación
        """
        # Validar que los bins existan y estén disponibles
        bin_ids = data.get('bin_ids', [])
        if not bin_ids:
            raise serializers.ValidationError("Debe proporcionar al menos un bin para transformar")
        
        bins = FruitBin.objects.filter(uid__in=bin_ids)
        if bins.count() != len(bin_ids):
            raise serializers.ValidationError("Uno o más bins no existen")
            
        # Validar el proveedor si se proporciona
        from .models import Supplier
        proveedor_id = data.get('proveedor')
        if proveedor_id:
            try:
                proveedor = Supplier.objects.get(uid=proveedor_id)
                data['proveedor_obj'] = proveedor
            except Supplier.DoesNotExist:
                raise serializers.ValidationError({"proveedor": f"No se encontró un proveedor con el ID {proveedor_id}"})
        else:
            data['proveedor_obj'] = None
        
        # Verificar que los bins estén en estados válidos para transformar
        unavailable_bins = bins.exclude(estado__in=['DISPONIBLE', 'EN_PROCESO'])
        if unavailable_bins.exists():
            unavailable_codes = [bin.codigo for bin in unavailable_bins]
            raise serializers.ValidationError(f"Los siguientes bins no están en un estado válido (DISPONIBLE o EN_PROCESO): {', '.join(unavailable_codes)}")
        
        # Verificar que todos los bins sean del mismo producto
        producto_id = bins.first().producto_id
        if bins.exclude(producto_id=producto_id).exists():
            raise serializers.ValidationError("Todos los bins deben ser del mismo producto")
        
        # Validar que el tipo de caja exista
        try:
            box_type = BoxType.objects.get(uid=data['box_type_id'])
            data['box_type'] = box_type
        except BoxType.DoesNotExist:
            raise serializers.ValidationError("El tipo de caja especificado no existe")
        
        # Calcular pesos disponibles en bins
        from decimal import Decimal
        total_neto_bins = sum((bin.peso_bruto - bin.peso_tara) for bin in bins)
        data['total_neto_bins'] = total_neto_bins
        
        # Aplicar restricciones según el tipo de caja
        box_type_nombre = box_type.nombre.lower()
        # La capacidad de contenido por caja define el peso neto esperado
        if not box_type.capacidad_por_caja or box_type.capacidad_por_caja <= 0:
            raise serializers.ValidationError("El tipo de caja seleccionado no tiene definida la capacidad_por_caja (kg por caja de producto)")
        peso_neto_esperado = box_type.capacidad_por_caja * data['cantidad_cajas']
        
        # Restricciones para diferentes tipos de cajas
        if 'rejilla' in box_type_nombre:
            max_cajas = 120
            max_peso = 1200  # kg
            if data['cantidad_cajas'] > max_cajas:
                raise serializers.ValidationError(f"Para cajas tipo rejilla, el máximo es {max_cajas} cajas")
            if peso_neto_esperado > max_peso:
                raise serializers.ValidationError(f"Para cajas tipo rejilla, el peso máximo es {max_peso} kg. Peso solicitado: {peso_neto_esperado} kg")
        elif 'toro' in box_type_nombre:
            max_cajas = 56
            peso_por_caja_ref = 18  # kg
            max_peso = max_cajas * peso_por_caja_ref
            if data['cantidad_cajas'] > max_cajas:
                raise serializers.ValidationError(f"Para cajas tipo toro, el máximo es {max_cajas} cajas")
            if peso_neto_esperado > max_peso:
                raise serializers.ValidationError(f"Para cajas tipo toro, el peso máximo es {max_peso} kg (18 kg por caja). Peso solicitado: {peso_neto_esperado} kg")
        
        # Validar que la capacidad por caja no sea irreal
        if box_type.capacidad_por_caja > 30:
            raise serializers.ValidationError(f"La capacidad por caja definida ({box_type.capacidad_por_caja} kg) es demasiado alta. Revise el tipo de caja.")
        
        # Añadir los bins al contexto para usarlos en create
        data['bins'] = bins
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        """
        Crear un nuevo lote (pallet) a partir de los bins seleccionados
        """
        bins = validated_data.pop('bins')
        box_type = validated_data.pop('box_type')
        from decimal import Decimal, ROUND_HALF_UP
        total_neto_bins = validated_data.pop('total_neto_bins')
        box_type_id = validated_data.pop('box_type_id')
        
        # Obtener el primer bin como referencia
        bin_referencia = bins.first()
        
        # Si es un producto tipo palta, se maneja por peso
        es_palta = bin_referencia.producto.tipo_producto == 'palta'
        
        # Calcular el peso neto del lote como cantidad_cajas * capacidad_por_caja (peso de producto por caja)
        peso_neto = (Decimal(validated_data['cantidad_cajas']) * box_type.capacidad_por_caja).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if peso_neto <= 0:
            raise serializers.ValidationError("El peso neto calculado del lote debe ser positivo")
        if peso_neto > total_neto_bins:
            raise serializers.ValidationError("El peso neto del lote excede el peso neto disponible en los bins seleccionados")
        
        # Calcular unidades por caja si es producto tipo 'otro'
        unidades_por_caja = 0
        cantidad_unidades = 0
        if not es_palta:
            # Para productos que no son palta, asumimos que se manejan por unidades
            # El usuario debería proporcionar este valor, pero aquí usamos un valor por defecto
            unidades_por_caja = 12  # Valor por defecto, idealmente vendría del frontend
            cantidad_unidades = validated_data['cantidad_cajas'] * unidades_por_caja
        
        # Crear el nuevo lote
        # Usar el proveedor proporcionado en la solicitud si está disponible, de lo contrario usar el del bin
        proveedor = validated_data.get('proveedor_obj') or bin_referencia.proveedor
        
        # Tara total por cajas (sin considerar pallet_type, que puede ser None)
        tara_total = (box_type.peso_caja * validated_data['cantidad_cajas']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        nuevo_lote = FruitLot.objects.create(
            producto=bin_referencia.producto,
            marca=bin_referencia.variedad or "",
            proveedor=proveedor,
            procedencia=proveedor.direccion if proveedor and proveedor.direccion else "No especificada",
            pais="Chile",  # Valor por defecto
            calibre=validated_data['calibre'],
            box_type=box_type,
            cantidad_cajas=validated_data['cantidad_cajas'],
            # Peso bruto = neto + tara de cajas
            peso_bruto=(peso_neto + tara_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            peso_neto=peso_neto,
            business=bin_referencia.business,
            fecha_ingreso=timezone.now().date(),
            estado_maduracion='verde',  # Valor por defecto
            costo_inicial=validated_data['costo_inicial'],
            costo_diario_almacenaje=0,  # Valor por defecto
            porcentaje_perdida_estimado=0,  # Valor por defecto
            precio_sugerido_min=validated_data.get('precio_sugerido_min'),
            precio_sugerido_max=validated_data.get('precio_sugerido_max'),
            # Campos para productos tipo 'otro'
            unidades_por_caja=unidades_por_caja,
            cantidad_unidades=cantidad_unidades
        )
        
        # Registrar el cambio de estado de maduración inicial
        from .models import MadurationHistory
        MadurationHistory.objects.create(
            lote=nuevo_lote,
            estado_maduracion=nuevo_lote.estado_maduracion
        )
        
        # Descontar kilos de forma secuencial: consumir completamente el primer bin, y el resto del siguiente, etc.
        # Orden propuesto: bins con mayor neto primero para minimizar parciales
        neto_restante = peso_neto
        bins_list = sorted(list(bins), key=lambda b: (b.peso_bruto - b.peso_tara), reverse=True)
        detalles_snapshot = []  # (bin, peso_bruto_previo, peso_tara_previa, kg_descontados)
        total_neto_consumido = Decimal('0.00')
        for bin in bins_list:
            if neto_restante <= 0:
                break
            bin_neto_actual = (bin.peso_bruto - bin.peso_tara)
            kg_a_descontar = bin_neto_actual if bin_neto_actual <= neto_restante else neto_restante

            # Guardar snapshot previo
            peso_bruto_previo = bin.peso_bruto
            peso_tara_previa = bin.peso_tara
            detalles_snapshot.append((bin, peso_bruto_previo, peso_tara_previa, kg_a_descontar))

            # Aplicar descuento
            bin.peso_bruto = (bin.peso_bruto - kg_a_descontar).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            # Normalizar y actualizar estado
            if (bin.peso_bruto - bin.peso_tara) <= 0:
                bin.peso_bruto = bin.peso_tara
                bin.estado = 'TRANSFORMADO'
            else:
                bin.estado = 'EN_PROCESO'
            bin.save(update_fields=['peso_bruto', 'estado'])

            neto_restante = (neto_restante - kg_a_descontar).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_neto_consumido = (total_neto_consumido + kg_a_descontar).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if neto_restante > 0:
            # No alcanzó el neto requerido
            raise serializers.ValidationError("El peso neto requerido excede el peso disponible en los bins seleccionados")
        
        # Registrar la transformación para mantener la trazabilidad
        # Calcular merma como diferencia entre neto de bins y neto del lote
        merma_calc = (total_neto_bins - peso_neto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Calcular merma como diferencia entre neto consumido y neto resultante (si hubiera ajuste)
        merma_calc = (total_neto_consumido - peso_neto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        transformacion = BinToLotTransformation.objects.create(
            lote=nuevo_lote,
            cantidad_cajas_resultantes=validated_data['cantidad_cajas'],
            peso_total_bins=total_neto_consumido,
            peso_neto_resultante=peso_neto,
            merma=merma_calc,
            business=bin_referencia.business
        )
        
        # Registrar los detalles de cada bin utilizado
        for bin, peso_bruto_previo, peso_tara_previa, kg_desc in detalles_snapshot:
            BinToLotTransformationDetail.objects.create(
                transformacion=transformacion,
                bin=bin,
                peso_bruto_previo=peso_bruto_previo,
                peso_tara_previa=peso_tara_previa,
                kg_descontados=kg_desc
            )
        
        return nuevo_lote

class BinToLotResponseSerializer(serializers.ModelSerializer):
    """
    Serializador para la respuesta de transformación de bins a lotes
    """
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    
    class Meta:
        model = FruitLot
        fields = [
            'uid', 'producto', 'producto_nombre', 'calibre', 'cantidad_cajas',
            'peso_bruto', 'peso_neto', 'fecha_ingreso',
            'costo_inicial', 'precio_sugerido_min', 'precio_sugerido_max'
        ]
