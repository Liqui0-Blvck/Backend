import uuid
from django.db import models
from core.models import BaseModel
from simple_history.models import HistoricalRecords
# No importar modelos de otras apps arriba para evitar ciclos

class Shift(BaseModel):
    ESTADO_CHOICES = [
        ("abierto", "Abierto"),
        ("cerrado", "Cerrado"),
    ]
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    usuario_abre = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name="shifts_abiertos")
    usuario_cierra = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name="shifts_cerrados", null=True, blank=True)
    fecha_apertura = models.DateTimeField()
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default="abierto")
    motivo_diferencia = models.TextField(blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"Turno {self.id} - {self.estado}"
