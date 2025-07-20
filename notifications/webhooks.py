import json
import requests
from django.conf import settings
from django.db import models

class WebhookSubscription(models.Model):
    """Modelo para almacenar suscripciones a webhooks"""
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='webhook_subscriptions')
    url = models.URLField(max_length=255)
    secret_key = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    # Tipos de eventos a los que está suscrito
    anuncios = models.BooleanField(default=True)
    inventario = models.BooleanField(default=True)
    ventas = models.BooleanField(default=True)
    turnos = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('business', 'url')
    
    def __str__(self):
        return f"{self.business.nombre} - {self.url}"


def send_webhook_notification(business_id, event_type, data):
    """
    Envía una notificación a todos los webhooks suscritos para un negocio y tipo de evento.
    
    Args:
        business_id: ID del negocio
        event_type: Tipo de evento ('anuncios', 'inventario', 'ventas', 'turnos')
        data: Datos a enviar en la notificación
    """
    # Obtener todas las suscripciones activas para este negocio y tipo de evento
    subscriptions = WebhookSubscription.objects.filter(
        business_id=business_id,
        is_active=True,
        **{event_type: True}  # Filtrar por el tipo de evento
    )
    
    if not subscriptions.exists():
        return
    
    # Preparar el payload
    payload = {
        'event_type': event_type,
        'business_id': business_id,
        'data': data
    }
    
    # Enviar la notificación a cada webhook suscrito
    for subscription in subscriptions:
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-FruitPOS-Webhook-Secret': subscription.secret_key
            }
            
            response = requests.post(
                subscription.url,
                data=json.dumps(payload),
                headers=headers,
                timeout=5  # Timeout de 5 segundos
            )
            
            # Registrar el resultado (podría guardarse en un log)
            success = 200 <= response.status_code < 300
            print(f"Webhook notification sent to {subscription.url}: {'Success' if success else 'Failed'}")
            
        except Exception as e:
            print(f"Error sending webhook notification to {subscription.url}: {str(e)}")
