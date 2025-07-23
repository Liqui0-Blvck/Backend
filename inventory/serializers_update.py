from rest_framework import serializers
from .models import FruitLot

class FruitLotSuggestedPriceUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar los precios sugeridos de un lote de fruta
    """
    class Meta:
        model = FruitLot
        fields = ('precio_sugerido_min', 'precio_sugerido_max')


class FruitLotMaturationUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar el estado de maduración de un lote de fruta
    """
    class Meta:
        model = FruitLot
        fields = ('estado_maduracion', 'fecha_maduracion')
