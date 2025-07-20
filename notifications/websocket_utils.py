import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

def send_notification_to_websocket(notification):
    """
    Envía una notificación a través del WebSocket a los grupos de usuario y negocio.

    Args:
        notification: La instancia de la notificación a enviar.
    """
    channel_layer = get_channel_layer()
    
    if channel_layer is None:
        logger.warning("No se encontró el channel_layer de Channels.")
        return
    
    try:
        # Serializar la notificación. El emisor ya está en el objeto `notification`.
        notification_data = NotificationSerializer(notification).data
        
        # Enviar al grupo del usuario específico
        user_group_name = f'notifications_user_{notification.usuario.id}'
        logger.debug(f"Enviando notificación al grupo de usuario: {user_group_name}")
        async_to_sync(channel_layer.group_send)(
            user_group_name,
            {
                'type': 'notification_message',
                'message': notification_data
            }
        )
        
        # Si la notificación está asociada a un negocio, enviar también al grupo del negocio
        if hasattr(notification.usuario, 'perfil') and notification.usuario.perfil.business:
            business_id = notification.usuario.perfil.business.id
            business_group_name = f'notifications_business_{business_id}'
            logger.debug(f"Enviando notificación al grupo de negocio: {business_group_name}")
            async_to_sync(channel_layer.group_send)(
                business_group_name,
                {
                    'type': 'notification_message',
                    'message': notification_data
                }
            )
    except Exception as e:
        logger.error(f"Error al enviar notificación por WebSocket: {e}", exc_info=True)
