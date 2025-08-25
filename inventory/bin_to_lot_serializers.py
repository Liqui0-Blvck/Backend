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
        
        # Verificar que todos los bins estén disponibles
        unavailable_bins = bins.exclude(estado='DISPONIBLE')
        if unavailable_bins.exists():
            unavailable_codes = [bin.codigo for bin in unavailable_bins]
            raise serializers.ValidationError(f"Los siguientes bins no están disponibles: {', '.join(unavailable_codes)}")
        
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
        
        # Calcular el peso total de los bins seleccionados
        peso_total = sum(bin.peso_bruto for bin in bins)
        data['peso_total'] = peso_total
        
        # Aplicar restricciones según el tipo de caja
        box_type_nombre = box_type.nombre.lower()
        
        # Restricciones para diferentes tipos de cajas
        if 'rejilla' in box_type_nombre:
            # Restricciones para cajas tipo rejilla
            max_cajas = 120
            max_peso = 1200  # kg
            
            if data['cantidad_cajas'] > max_cajas:
                raise serializers.ValidationError(f"Para cajas tipo rejilla, el máximo es {max_cajas} cajas")
            
            if peso_total > max_peso:
                raise serializers.ValidationError(f"Para cajas tipo rejilla, el peso máximo es {max_peso} kg. Peso actual: {peso_total} kg")
        
        elif 'toro' in box_type_nombre:
            # Restricciones para cajas tipo toro
            max_cajas = 56
            peso_por_caja = 18  # kg
            max_peso = max_cajas * peso_por_caja
            
            if data['cantidad_cajas'] > max_cajas:
                raise serializers.ValidationError(f"Para cajas tipo toro, el máximo es {max_cajas} cajas")
            
            if peso_total > max_peso:
                raise serializers.ValidationError(f"Para cajas tipo toro, el peso máximo es {max_peso} kg (18 kg por caja). Peso actual: {peso_total} kg")
        
        # Validar que la cantidad de cajas sea razonable según el peso
        peso_promedio_por_caja = peso_total / data['cantidad_cajas'] if data['cantidad_cajas'] > 0 else 0
        if peso_promedio_por_caja > 25:  # Asumiendo un límite razonable de 25kg por caja
            raise serializers.ValidationError(f"El peso promedio por caja ({peso_promedio_por_caja:.2f} kg) es demasiado alto. Revise la cantidad de cajas o el peso total.")
        
        # Añadir los bins al contexto para usarlos en create
        data['bins'] = bins
        data['peso_total'] = peso_total
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        """
        Crear un nuevo lote (pallet) a partir de los bins seleccionados
        """
        bins = validated_data.pop('bins')
        box_type = validated_data.pop('box_type')
        peso_total = validated_data.pop('peso_total')
        box_type_id = validated_data.pop('box_type_id')
        
        # Obtener el primer bin como referencia
        bin_referencia = bins.first()
        
        # Calcular el peso de tara para el nuevo lote
        peso_tara = (box_type.peso_caja * validated_data['cantidad_cajas'])
        
        # Si es un producto tipo palta, se maneja por peso
        es_palta = bin_referencia.producto.tipo_producto == 'palta'
        
        # Calcular el peso neto
        peso_neto = peso_total - peso_tara
        
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
        
        nuevo_lote = FruitLot.objects.create(
            producto=bin_referencia.producto,
            marca=bin_referencia.variedad or "",
            proveedor=proveedor,
            procedencia=proveedor.direccion if proveedor and proveedor.direccion else "No especificada",
            pais="Chile",  # Valor por defecto
            calibre=validated_data['calibre'],
            box_type=box_type,
            cantidad_cajas=validated_data['cantidad_cajas'],
            peso_bruto=peso_total,
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
        
        # Actualizar el estado de los bins a TRANSFORMADO
        bins.update(estado='TRANSFORMADO')
        
        # Registrar la transformación para mantener la trazabilidad
        transformacion = BinToLotTransformation.objects.create(
            lote=nuevo_lote,
            cantidad_cajas_resultantes=validated_data['cantidad_cajas'],
            peso_total_bins=peso_total,
            peso_neto_resultante=peso_neto,
            merma=0,  # La merma se podría calcular si tenemos más información
            business=bin_referencia.business
        )
        
        # Registrar los detalles de cada bin utilizado
        for bin in bins:
            BinToLotTransformationDetail.objects.create(
                transformacion=transformacion,
                bin=bin,
                peso_bruto=bin.peso_bruto,
                peso_tara=bin.peso_tara
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
