from django.db import models
from .models import BaseModel, FruitBin, FruitLot
import uuid

class BinToLotTransformation(BaseModel):
    """
    Modelo para registrar la transformación de bins a lotes (pallets)
    y mantener la trazabilidad entre ellos.
    """
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    
    # Relación con el lote (pallet) creado
    lote = models.ForeignKey(
        'FruitLot',
        on_delete=models.CASCADE,
        related_name='transformaciones_origen'
    )
    
    # Metadatos de la transformación
    fecha_transformacion = models.DateTimeField(auto_now_add=True)
    cantidad_cajas_resultantes = models.PositiveIntegerField()
    peso_total_bins = models.DecimalField(max_digits=10, decimal_places=2)
    peso_neto_resultante = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Merma calculada (diferencia entre peso total de bins y peso neto resultante)
    merma = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Observaciones adicionales
    observaciones = models.TextField(blank=True, null=True)
    
    # Relación con el negocio
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    
    def __str__(self):
        return f"Transformación {self.id} - Lote {self.lote.id}"
    
    class Meta:
        verbose_name = "Transformación de Bin a Lote"
        verbose_name_plural = "Transformaciones de Bins a Lotes"


class BinToLotTransformationDetail(models.Model):
    """
    Detalle de los bins utilizados en una transformación a lote (pallet)
    """
    transformacion = models.ForeignKey(
        BinToLotTransformation,
        on_delete=models.CASCADE,
        related_name='detalles'
    )
    
    bin = models.ForeignKey(
        'FruitBin',
        on_delete=models.CASCADE,
        related_name='transformaciones'
    )
    
    # Peso del bin al momento de la transformación
    peso_bruto = models.DecimalField(max_digits=10, decimal_places=2)
    peso_tara = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"Detalle {self.id} - Bin {self.bin.codigo}"
    
    @property
    def peso_neto(self):
        """Calcula el peso neto del bin"""
        return self.peso_bruto - self.peso_tara
    
    class Meta:
        verbose_name = "Detalle de Transformación"
        verbose_name_plural = "Detalles de Transformaciones"
