from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal

from announcements.models import Announcement
from .models import Notification
from business.models import Business
from .webhooks import send_webhook_notification
from .websocket_utils import send_notification_to_websocket

from accounts.models import CustomUser
from inventory.models import FruitLot
from sales.models import Sale
from shifts.models import Shift

def get_notification_recipients(business: Business, roles: list, exclude_user: CustomUser = None):
    """
    Obtiene una lista unificada de destinatarios para notificaciones.
    Busca por rol (con perfil), como dueño del negocio, y como staff del negocio sin perfil.
    """
    if not business:
        return CustomUser.objects.none()

    recipient_ids = set()

    # 1. Dueño del negocio
    if business.owner:
        recipient_ids.add(business.owner.id)

    # 2. Usuarios con roles específicos y perfil en el negocio
    users_with_role_and_profile = CustomUser.objects.filter(
        perfil__business=business, groups__name__in=roles
    )
    recipient_ids.update(u.id for u in users_with_role_and_profile)

    # 3. Usuarios con rol, que son staff pero sin perfil (caso admin principal)
    users_with_role_no_profile = CustomUser.objects.filter(
        groups__name__in=roles, is_staff=True, perfil__isnull=True
    )
    # Asumimos que un staff sin perfil puede pertenecer a cualquier negocio
    recipient_ids.update(u.id for u in users_with_role_no_profile)

    # Excluir al usuario que origina la acción
    if exclude_user and exclude_user.id in recipient_ids:
        recipient_ids.remove(exclude_user.id)

    return CustomUser.objects.filter(id__in=recipient_ids)

@receiver(post_save, sender=Announcement)
def create_announcement_notification(sender, instance, created, **kwargs):
    """Notifica a todos los usuarios del negocio sobre un anuncio, excluyendo al creador."""
    if not instance.business:
        return

    if instance.estado == 'activo' or (instance.estado == 'programado' and instance.fecha_inicio <= timezone.now()):
        usuarios_a_notificar = CustomUser.objects.filter(perfil__business=instance.business).distinct()
        action = "Nuevo" if created else "Actualización de"
        for usuario in usuarios_a_notificar:
            if usuario != instance.creador:
                Notification.objects.create(
                    usuario=usuario, emisor=instance.creador,
                    titulo=f"{action} anuncio: {instance.titulo}",
                    mensaje=instance.contenido[:200] + ("..." if len(instance.contenido) > 200 else ""),
                    tipo="anuncio", enlace=f"/anuncios/{instance.uid}/",
                    objeto_relacionado_tipo="announcement", objeto_relacionado_id=str(instance.uid)
                )
        # Webhook y Websocket se manejan en otro signal/lógica para Notification

@receiver(post_save, sender=FruitLot)
def check_low_stock(sender, instance, created, **kwargs):
    """Notifica a admins y supervisores sobre stock bajo."""
    if not created and instance.business:
        umbral_porcentaje = 0.10
        umbral_absoluto = 20
        # Convertimos explícitamente a float para evitar problemas de tipo
        peso_inicial = float(instance.peso_neto or 0)  # Usamos peso_neto como peso inicial
        peso_disponible = float(instance.peso_disponible() or 0)  # Llamamos al método peso_disponible()
        porcentaje_disponible = (peso_disponible / peso_inicial) if peso_inicial > 0 else 0
        
        if porcentaje_disponible <= umbral_porcentaje or peso_disponible <= umbral_absoluto:
            if not Notification.objects.filter(tipo='stock_bajo', objeto_relacionado_id=str(instance.id)).exists():
                recipients = get_notification_recipients(instance.business, ['administrador', 'supervisor'])
                emisor = instance.business.owner or recipients.first()
                nombre_producto = instance.producto.nombre if instance.producto else "Producto desconocido"
                for user in recipients:
                    Notification.objects.create(
                        usuario=user, emisor=emisor,
                        titulo=f"Stock bajo: {nombre_producto}",
                        mensaje=f"El lote {instance.codigo} tiene poco stock. Quedan {peso_disponible:.2f} kg.",
                        tipo="stock_bajo", enlace=f"/inventario/lotes/{instance.id}/",
                        objeto_relacionado_tipo="fruitlot", objeto_relacionado_id=str(instance.id)
                    )

@receiver(post_save, sender=Sale)
def notify_important_sale(sender, instance, created, **kwargs):
    """Notifica a admins y supervisores sobre ventas importantes, excluyendo al vendedor."""
    if created and instance.business:
        umbral_monto = Decimal('100000')
        if instance.total >= umbral_monto:
            recipients = get_notification_recipients(instance.business, ['administrador', 'supervisor'], exclude_user=instance.vendedor)
            for user in recipients:
                Notification.objects.create(
                    usuario=user, emisor=instance.vendedor,
                    titulo=f"Venta importante: ${instance.total:,.0f}",
                    mensaje=f"Venta de ${instance.total:,.0f} por {instance.vendedor.get_full_name_or_email() if instance.vendedor else 'N/A'}.",
                    tipo="venta_importante", enlace=f"/ventas/{instance.id}/",
                    objeto_relacionado_tipo="sale", objeto_relacionado_id=str(instance.id)
                )

@receiver(post_save, sender=Shift)
def crear_notificacion_inicio_turno(sender, instance, created, **kwargs):
    """Notifica a admins y supervisores sobre el inicio de un turno, excluyendo al emisor."""
    if created and instance.estado == 'abierto':
        if not hasattr(instance, 'caja') or not instance.caja.business or not hasattr(instance, 'usuario_apertura'):
            return
        recipients = get_notification_recipients(instance.caja.business, ['administrador', 'supervisor'], exclude_user=instance.usuario_apertura)
        for user in recipients:
            Notification.objects.create(
                usuario=user, emisor=instance.usuario_apertura,
                titulo="Inicio de Turno",
                mensaje=f"{instance.usuario_apertura.get_full_name_or_email()} ha iniciado turno en {instance.caja.nombre}.",
                tipo='turno_iniciado', objeto_relacionado_tipo='shift',
                objeto_relacionado_id=str(instance.id)
            )

@receiver(post_save, sender=Notification)
def dispatch_notification(sender, instance, created, **kwargs):
    """Envía la notificación por WebSocket y Webhook después de ser creada."""
    if created:
        send_notification_to_websocket(instance)
        
        # Preparar y enviar webhook
        if instance.usuario.perfil and instance.usuario.perfil.business:
            webhook_data = {
                'notification_id': str(instance.uid),
                'user_email': instance.usuario.email,
                'title': instance.titulo,
                'message': instance.mensaje,
                'type': instance.tipo,
                'created_at': instance.created_at.isoformat(),
            }
            # El event_type debe coincidir con los campos booleanos del modelo WebhookSubscription
            # Por ejemplo, si instance.tipo es 'anuncio', el event_type debe ser 'anuncios'.
            event_map = {
                'anuncio': 'anuncios',
                'stock_bajo': 'inventario',
                'venta_importante': 'ventas',
                'turno_iniciado': 'turnos',
            }
            event_type = event_map.get(instance.tipo)

            if event_type:
                send_webhook_notification(
                    business_id=instance.usuario.perfil.business.id,
                    event_type=event_type,
                    data=webhook_data
                )
