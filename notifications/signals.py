from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.utils import timezone
from django.db.models import F, Sum, Q
from decimal import Decimal

from announcements.models import Announcement
from .models import Notification
from .webhooks import send_webhook_notification
from .websocket_utils import send_notification_to_websocket

# Importamos los modelos necesarios
from accounts.models import CustomUser
from inventory.models import FruitLot, Product
from sales.models import Sale
from shifts.models import Shift

@receiver(post_save, sender=Announcement)
def create_announcement_notification(sender, instance, created, **kwargs):
    """
    Crea notificaciones para los usuarios cuando se crea o actualiza un anuncio.
    
    Args:
        sender: El modelo que envió la señal (Announcement)
        instance: La instancia del anuncio que fue guardada
        created: Booleano que indica si el anuncio fue creado o actualizado
    """
    # Solo notificar si el anuncio está activo o programado con fecha de inicio <= ahora
    if instance.estado == 'activo' or (instance.estado == 'programado' and instance.fecha_inicio <= timezone.now()):
        # Obtener todos los usuarios del negocio, excluyendo a los administradores
        usuarios_a_notificar = CustomUser.objects.filter(
            perfil__business=instance.business
        ).exclude(groups__name='Administrador').distinct()
        
        # Crear una notificación para cada usuario
        action = "Nuevo" if created else "Actualización de"
        for usuario in usuarios_a_notificar:
            # Evitar notificar al creador del anuncio
            if usuario != instance.creador:
                notification = Notification.objects.create(
                    usuario=usuario,
                    emisor=instance.creador,
                    titulo=f"{action} anuncio: {instance.titulo}",
                    mensaje=instance.contenido[:200] + ("..." if len(instance.contenido) > 200 else ""),
                    tipo="anuncio",
                    enlace=f"/anuncios/{instance.uid}/",
                    objeto_relacionado_tipo="announcement",
                    objeto_relacionado_id=str(instance.uid)
                )
                
                # Enviar notificación por WebSocket
                send_notification_to_websocket(notification)
        
        # Enviar notificación por webhook
        webhook_data = {
            'id': str(instance.uid),
            'titulo': instance.titulo,
            'tipo': instance.tipo,
            'estado': instance.estado,
            'destacado': instance.destacado,
            'requiere_confirmacion': instance.requiere_confirmacion,
            'fecha_inicio': str(instance.fecha_inicio),
            'action': 'created' if created else 'updated'
        }
        
        send_webhook_notification(
            business_id=instance.business.id,
            event_type='anuncios',
            data=webhook_data
        )

@receiver(post_save, sender=FruitLot)
def check_low_stock(sender, instance, created, **kwargs):
    """
    Verifica si un lote tiene stock bajo y envía notificaciones.
    """
    # Solo verificar si el lote ya existe (no es nuevo) y tiene peso disponible bajo
    if not created and instance.peso_disponible is not None:
        # Definir umbral de stock bajo (por ejemplo, 10% del peso inicial o menos de 20kg)
        umbral_porcentaje = 0.10  # 10% del peso inicial
        umbral_absoluto = 20  # 20 kg
        
        peso_inicial = instance.peso_inicial or 0
        peso_disponible = instance.peso_disponible or 0
        
        # Verificar si está por debajo del umbral
        porcentaje_disponible = (peso_disponible / peso_inicial) if peso_inicial > 0 else 0
        
        if porcentaje_disponible <= umbral_porcentaje or peso_disponible <= umbral_absoluto:
            # Solo notificar si no se ha notificado antes por este lote
            # (podríamos usar un campo en el modelo o verificar notificaciones existentes)
            notificacion_existente = Notification.objects.filter(
                tipo='stock_bajo',
                objeto_relacionado_tipo='fruitlot',
                objeto_relacionado_id=str(instance.id)
            ).exists()
            
            if not notificacion_existente:
                # Obtener administradores y supervisores del negocio
                grupos_objetivo = ['administrador', 'supervisor']
                usuarios_a_notificar = CustomUser.objects.filter(
                    perfil__business=instance.business,
                    groups__name__in=grupos_objetivo
                ).distinct()
                
                # Crear notificaciones
                nombre_producto = instance.product.nombre if instance.product else "Producto desconocido"

                # Asignar al dueño del negocio como emisor. Si no hay dueño, al primer admin.
                emisor_notificacion = None
                if instance.business:
                    emisor_notificacion = instance.business.owner
                    if not emisor_notificacion:
                        # Si no hay dueño, buscar el primer administrador del negocio
                        admin_group = Group.objects.get(name='administrador')
                        emisor_notificacion = CustomUser.objects.filter(
                            perfil__business=instance.business, 
                            groups=admin_group
                        ).first()

                for usuario in usuarios_a_notificar:
                    notification = Notification.objects.create(
                        usuario=usuario,
                        emisor=emisor_notificacion,
                        titulo=f"Stock bajo: {nombre_producto}",
                        mensaje=f"El lote {instance.codigo} de {nombre_producto} tiene un stock bajo. "
                                f"Quedan {peso_disponible:.2f} kg disponibles ({porcentaje_disponible*100:.1f}% del inicial).",
                        tipo="stock_bajo",
                        enlace=f"/inventario/lotes/{instance.id}/",
                        objeto_relacionado_tipo="fruitlot",
                        objeto_relacionado_id=str(instance.id)
                    )
                    
                    # Enviar notificación por WebSocket
                    send_notification_to_websocket(notification)
                
                # Enviar notificación por webhook
                webhook_data = {
                    'id': instance.id,
                    'codigo': instance.codigo,
                    'producto': nombre_producto,
                    'peso_inicial': float(peso_inicial),
                    'peso_disponible': float(peso_disponible),
                    'porcentaje_disponible': float(porcentaje_disponible),
                    'business_id': instance.business.id if instance.business else None
                }
                
                if instance.business:
                    send_webhook_notification(
                        business_id=instance.business.id,
                        event_type='inventario',
                        data=webhook_data
                    )

@receiver(post_save, sender=Sale)
def notify_important_sale(sender, instance, created, **kwargs):
    """
    Notifica sobre ventas importantes (por monto o cantidad).
    """
    if created:  # Solo para ventas nuevas
        # Definir umbral para ventas importantes (por ejemplo, más de $100,000)
        umbral_monto = Decimal('100000')  # $100,000
        
        # Verificar si la venta supera el umbral
        if instance.total >= umbral_monto:
            # Obtener administradores del negocio
            grupos_objetivo = ['administrador']
            usuarios_a_notificar = CustomUser.objects.filter(
                perfil__business=instance.business,
                groups__name__in=grupos_objetivo
            ).distinct()
            
            # Crear notificaciones
            for usuario in usuarios_a_notificar:
                notification = Notification.objects.create(
                    usuario=usuario,
                    emisor=instance.vendedor,
                    titulo=f"Venta importante: ${instance.total:,.0f}",
                    mensaje=f"Se ha registrado una venta importante por ${instance.total:,.0f} "
                            f"al cliente {instance.cliente_nombre or 'Sin nombre'}.",
                    tipo="venta_importante",
                    enlace=f"/ventas/{instance.id}/",
                    objeto_relacionado_tipo="sale",
                    objeto_relacionado_id=str(instance.id)
                )
                
                # Enviar notificación por WebSocket
                send_notification_to_websocket(notification)
            
            # Enviar notificación por webhook
            webhook_data = {
                'id': instance.id,
                'total': float(instance.total),
                'cliente': instance.cliente_nombre,
                'fecha': str(instance.fecha),
                'vendedor': instance.vendedor.email if instance.vendedor else None,
                'business_id': instance.business.id if instance.business else None
            }
            
            if instance.business:
                send_webhook_notification(
                    business_id=instance.business.id,
                    event_type='ventas',
                    data=webhook_data
                )

@receiver(post_save, sender=Shift)
def crear_notificacion_inicio_turno(sender, instance, created, **kwargs):
    """
    Crea una notificación cuando un turno se inicia (estado='abierto').
    Notifica a todos los administradores y supervisores del negocio.
    """
    # Solo actuar si el turno es nuevo y está 'abierto'
    if created and instance.estado == 'abierto':
        # Asegurarse de que el turno tiene la información necesaria
        if not hasattr(instance, 'caja') or not instance.caja.business or not hasattr(instance, 'usuario_apertura'):
            return

        business = instance.caja.business
        emisor = instance.usuario_apertura

        # Obtener todos los administradores y supervisores del negocio, excluyendo al emisor
        recipients = CustomUser.objects.filter(
            perfil__business=business,
            groups__name__in=['administrador', 'supervisor']
        ).exclude(id=emisor.id).distinct()

        # Crear una notificación para cada destinatario
        for recipient in recipients:
            notification = Notification.objects.create(
                usuario=recipient,
                emisor=emisor,
                titulo="Inicio de Turno",
                mensaje=f"El usuario {emisor.get_full_name_or_email()} ha iniciado un nuevo turno en la caja {instance.caja.nombre}.",
                tipo='turno_iniciado',
                objeto_relacionado_tipo='shift',
                objeto_relacionado_id=str(instance.id)
            )
            send_notification_to_websocket(notification)

        # Opcional: Enviar un webhook general sobre el inicio del turno
        webhook_data = {
            'id': str(instance.id),
            'caja': instance.caja.nombre,
            'usuario_apertura': emisor.email,
            'fecha_apertura': str(instance.fecha_apertura),
            'estado': instance.estado,
            'action': 'opened',
            'business_id': business.id
        }
        send_webhook_notification(
            business_id=business.id,
            event_type='turnos',
            data=webhook_data
        )
