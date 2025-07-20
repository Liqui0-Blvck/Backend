from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar notificaciones."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.all()

    def get_queryset(self):
        """
        Filtra las notificaciones según el rol del usuario:
        - Administradores/Supervisores: Ven todas las notificaciones de su negocio, 
          excluyendo las que ellos mismos emiten.
        - Vendedores: Ven solo sus propias notificaciones.
        """
        user = self.request.user

        if not hasattr(user, 'perfil') or not user.perfil.business:
            # Si el usuario no tiene perfil o negocio, solo puede ver sus propias notificaciones.
            return Notification.objects.filter(usuario=user).distinct()

        business = user.perfil.business
        is_admin = user.groups.filter(name='administrador').exists()
        is_supervisor = user.groups.filter(name='supervisor').exists()

        if is_admin or is_supervisor:
            # Obtiene todos los usuarios que pertenecen al mismo negocio.
            usuarios_del_negocio = CustomUser.objects.filter(perfil__business=business)
            # Filtra las notificaciones cuyo destinatario está en esa lista,
            # excluyendo las que el propio admin/supervisor emitió.
            return Notification.objects.filter(
                usuario__in=usuarios_del_negocio
            ).exclude(emisor=user).distinct()
        else:
            # El resto de roles (ej. vendedor) solo ven sus propias notificaciones.
            return Notification.objects.filter(usuario=user).distinct()

    @action(detail=False, methods=['post'], url_path='mark-all-as-read')
    def mark_all_as_read(self, request):
        """Marca todas las notificaciones del usuario como leídas."""
        Notification.objects.filter(usuario=request.user, leida=False).update(leida=True, fecha_lectura=timezone.now())
        return Response({'status': 'Todas las notificaciones marcadas como leídas'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        """Marca una notificación específica como leída."""
        try:
            notification = self.get_object()
            if notification.usuario == request.user:
                notification.leida = True
                notification.fecha_lectura = timezone.now()
                notification.save()
                return Response({'status': 'Notificación marcada como leída'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'No tienes permiso para esta acción'}, status=status.HTTP_403_FORBIDDEN)
        except Notification.DoesNotExist:
            return Response({'error': 'Notificación no encontrada'}, status=status.HTTP_404_NOT_FOUND)
