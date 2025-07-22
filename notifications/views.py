from django.utils import timezone
from django.db.models import Q
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
        Filtra las notificaciones según el rol del usuario.
        - Administradores/Supervisores: Ven todas las notificaciones de su negocio.
        - Otros roles: Ven solo las notificaciones que les son asignadas directamente.
        """
        user = self.request.user
        
        # Determinar el negocio del usuario, incluso si no tiene perfil (caso admin)
        business = None
        if hasattr(user, 'perfil') and user.perfil.business:
            business = user.perfil.business
        elif user.groups.filter(name='administrador').exists() and Business.objects.exists():
            business = Business.objects.first()

        # Si no se puede determinar un negocio, devolver solo notificaciones personales
        if not business:
            return Notification.objects.filter(usuario=user).distinct()

        # Si el usuario es admin o supervisor, muestra todas las notificaciones del negocio
        if user.groups.filter(name__in=['administrador', 'supervisor']).exists() or user.is_superuser:
            return Notification.objects.filter(
                Q(emisor__perfil__business=business) | Q(usuario__perfil__business=business)
            ).distinct()
        else:
            # Otros roles solo ven las notificaciones dirigidas a ellos
            return Notification.objects.filter(usuario=user).distinct()
        
        # if user.groups.filter(name__in=['administrador', 'supervisor']).exists():
        #     # Los administradores y supervisores ven las notificaciones emitidas en su negocio
        #     # O las notificaciones que les son asignadas directamente a ellos.
        #     return Notification.objects.filter(
        #         Q(emisor__perfil__business=business) | Q(usuario=user)
        #     ).distinct()
        # else:
        #     # El resto de roles (ej. vendedor) solo ven sus propias notificaciones directas.
        #     return Notification.objects.filter(usuario=user).distinct()
        # is_admin = user.groups.filter(name='administrador').exists()
        # is_supervisor = user.groups.filter(name='supervisor').exists()

        # if is_admin or is_supervisor:
        #     # Obtiene todos los usuarios que pertenecen al mismo negocio.
        #     usuarios_del_negocio = CustomUser.objects.filter(perfil__business=business)
        #     # Filtra las notificaciones cuyo EMISOR pertenece al negocio.
        #     # Esto asegura que el admin/supervisor vea toda la actividad de su negocio.
        #     # El frontend se encargará de filtrar las que no quiera mostrar (ej. las propias).
        #     return Notification.objects.filter(
        #         emisor__perfil__business=business
        #     ).distinct()
        # else:
        #     # El resto de roles (ej. vendedor) solo ven sus propias notificaciones.
        #     return Notification.objects.filter(usuario=user).distinct()

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
