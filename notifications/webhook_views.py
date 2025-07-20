from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from core.permissions import IsAdminOrOwner
from .webhooks import WebhookSubscription
from .serializers import WebhookSubscriptionSerializer

class WebhookSubscriptionViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar suscripciones a webhooks"""
    queryset = WebhookSubscription.objects.all()
    serializer_class = WebhookSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwner]
    
    def get_queryset(self):
        """Filtrar suscripciones para mostrar solo las del negocio del usuario"""
        user = self.request.user
        return WebhookSubscription.objects.filter(business=user.perfil.business)
    
    def perform_create(self, serializer):
        """Asignar automáticamente el negocio del usuario al crear una suscripción"""
        serializer.save(business=self.request.user.perfil.business)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Activar o desactivar una suscripción a webhook"""
        subscription = self.get_object()
        subscription.is_active = not subscription.is_active
        subscription.save()
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Enviar una notificación de prueba al webhook"""
        from .webhooks import send_webhook_notification
        
        subscription = self.get_object()
        
        # Enviar una notificación de prueba
        test_data = {
            'message': 'Esta es una notificación de prueba',
            'timestamp': str(timezone.now())
        }
        
        try:
            send_webhook_notification(
                business_id=subscription.business.id,
                event_type='sistema',
                data=test_data
            )
            return Response({'status': 'success', 'message': 'Notificación de prueba enviada'})
        except Exception as e:
            return Response(
                {'status': 'error', 'message': f'Error al enviar la notificación: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
