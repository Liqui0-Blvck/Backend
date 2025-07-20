from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.utils import timezone

from .models import Announcement
from accounts.models import CustomUser

@receiver(post_save, sender=Announcement)
def notify_users_on_announcement(sender, instance, created, **kwargs):
    """
    Envía notificaciones a los usuarios cuando se crea o actualiza un anuncio.
    
    Args:
        sender: El modelo que envió la señal (Announcement)
        instance: La instancia del anuncio que fue guardada
        created: Booleano que indica si el anuncio fue creado o actualizado
    """
    # Solo notificar si el anuncio está activo o programado con fecha de inicio <= ahora
    if instance.estado == 'activo' or (instance.estado == 'programado' and instance.fecha_inicio <= timezone.now()):
        # Obtener los grupos de usuarios que deben recibir la notificación
        grupos_objetivo = ['vendedor', 'supervisor']
        
        # Obtener todos los usuarios del negocio que pertenecen a los grupos objetivo
        usuarios_a_notificar = CustomUser.objects.filter(
            perfil__business=instance.business,
            groups__name__in=grupos_objetivo
        ).distinct()
        
        # Aquí implementaríamos el envío de notificaciones
        # Por ahora, solo registramos en el log
        action = "creado" if created else "actualizado"
        print(f"Anuncio {action}: {instance.titulo}")
        print(f"Notificando a {usuarios_a_notificar.count()} usuarios")
        
        # Aquí se podría implementar el envío de notificaciones por correo, push, etc.
        for usuario in usuarios_a_notificar:
            print(f"Notificando a {usuario.email} sobre el anuncio: {instance.titulo}")
            
            # Ejemplo de cómo se podría enviar un correo electrónico
            # (requeriría configuración adicional)
            """
            send_mail(
                subject=f"Nuevo anuncio: {instance.titulo}",
                message=f"{instance.contenido}\n\nPor favor confirme la lectura de este anuncio.",
                from_email="notificaciones@fruitpos.com",
                recipient_list=[usuario.email],
                fail_silently=True,
            )
            """
            
            # Ejemplo de cómo se podría enviar una notificación push
            # (requeriría integración con un servicio de notificaciones)
            """
            send_push_notification(
                user_id=usuario.id,
                title=f"Nuevo anuncio: {instance.titulo}",
                body=instance.contenido[:100] + "...",
                data={
                    "announcement_id": str(instance.uid),
                    "type": instance.tipo,
                    "requires_confirmation": instance.requiere_confirmacion
                }
            )
            """
