from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

class FruitLotResult(models.Model):
    """
    Almacena los resultados reales de un lote de fruta después de su venta completa.
    Permite contrastar la predicción inicial con el resultado real.
    """
    fruitlot = models.OneToOneField('inventory.FruitLot', on_delete=models.CASCADE, related_name='resultado')
    fecha_venta_completa = models.DateTimeField(default=timezone.now)
    
    # Datos de predicción (copiados del lote al momento de creación)
    prediccion_costo_total = models.DecimalField(max_digits=12, decimal_places=2)
    prediccion_perdida_kg = models.DecimalField(max_digits=8, decimal_places=2)
    prediccion_perdida_porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    prediccion_ingreso_total = models.DecimalField(max_digits=12, decimal_places=2)
    prediccion_ganancia_total = models.DecimalField(max_digits=12, decimal_places=2)
    prediccion_margen = models.DecimalField(max_digits=5, decimal_places=2)
    prediccion_dias_estimados = models.PositiveIntegerField()
    
    # Datos reales (calculados al finalizar la venta)
    real_costo_total = models.DecimalField(max_digits=12, decimal_places=2)
    real_perdida_kg = models.DecimalField(max_digits=8, decimal_places=2)
    real_perdida_porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    real_ingreso_total = models.DecimalField(max_digits=12, decimal_places=2)
    real_ganancia_total = models.DecimalField(max_digits=12, decimal_places=2)
    real_margen = models.DecimalField(max_digits=5, decimal_places=2)
    real_dias_en_inventario = models.PositiveIntegerField()
    
    # Diferencias (calculadas)
    diferencia_costo = models.DecimalField(max_digits=12, decimal_places=2)
    diferencia_perdida_kg = models.DecimalField(max_digits=8, decimal_places=2)
    diferencia_perdida_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, help_text="Puntos porcentuales de diferencia")
    diferencia_ingreso = models.DecimalField(max_digits=12, decimal_places=2)
    diferencia_ganancia = models.DecimalField(max_digits=12, decimal_places=2)
    diferencia_margen = models.DecimalField(max_digits=5, decimal_places=2, help_text="Puntos porcentuales de diferencia")
    diferencia_dias = models.IntegerField(help_text="Diferencia entre días reales y estimados")
    
    # Metadatos
    notas = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    def __str__(self):
        return f"Resultados de {self.fruitlot}"
    
    class Meta:
        verbose_name = "Resultado de lote"
        verbose_name_plural = "Resultados de lotes"
