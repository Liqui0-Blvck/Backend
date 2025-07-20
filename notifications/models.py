import uuid
from django.db import models
from core.models import BaseModel
from .webhooks import WebhookSubscription  # Importamos el modelo de webhooks

class Notification(BaseModel):
    """Modelo para almacenar notificaciones para los usuarios"""
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    TIPO_CHOICES = [
        ('anuncio', 'Anuncio'),
        ('sistema', 'Sistema'),
        ('venta', 'Venta'),
        ('inventario', 'Inventario'),
        ('turno', 'Turno'),
        ('stock_bajo', 'Stock Bajo'),
        ('venta_importante', 'Venta Importante'),
        ('cambio_turno', 'Cambio de Turno'),
        ('turno_iniciado', 'Turno Iniciado'),
        ('producto_nuevo', 'Producto Nuevo'),
        ('precio_actualizado', 'Precio Actualizado'),
    ]
    
    usuario = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='notificaciones')  # Destinatario
    emisor = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='notificaciones_emitidas')  # Quién origina la acción
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='sistema')
    leida = models.BooleanField(default=False)
    fecha_lectura = models.DateTimeField(null=True, blank=True)
    enlace = models.CharField(max_length=255, blank=True, null=True)  # URL o ruta para navegar al hacer clic
    objeto_relacionado_tipo = models.CharField(max_length=50, blank=True, null=True)  # Tipo de objeto relacionado (ej: "announcement")
    objeto_relacionado_id = models.CharField(max_length=50, blank=True, null=True)  # ID del objeto relacionado
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
    
    def __str__(self):
        return f"{self.titulo} - {self.usuario.email}"
