from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Sale, CustomerPayment
from django.db import transaction
from django.utils import timezone

@receiver(post_save, sender=Sale)
def update_customer_credit(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar una venta.
    Si es una venta a crédito, verifica que el cliente tenga suficiente crédito disponible.
    """
    # Solo procesar si hay un cliente asociado y es una venta a crédito
    if instance.cliente and instance.metodo_pago == 'credito':
        # Si el cliente es un string (UID), buscar el objeto cliente
        if isinstance(instance.cliente, str):
            from .models import Customer
            try:
                cliente = Customer.objects.get(uid=instance.cliente)
            except Customer.DoesNotExist:
                print(f"ADVERTENCIA: No se encontró el cliente con UID {instance.cliente}")
                return
        else:
            cliente = instance.cliente
        
        # Si es una venta nueva, verificar el límite de crédito
        if created:
            # Verificar si el cliente tiene crédito activo
            if not cliente.credito_activo:
                # Aquí podrías lanzar una excepción o manejar el caso de alguna manera
                # Por ahora, solo registramos el evento
                print(f"ADVERTENCIA: Se registró una venta a crédito para {cliente.nombre} pero no tiene crédito activo")
                return
            
            # Verificar si el cliente tiene suficiente crédito disponible
            if cliente.limite_credito and instance.total > cliente.credito_disponible:
                # Aquí podrías lanzar una excepción o manejar el caso de alguna manera
                # Por ahora, solo registramos el evento
                print(f"ADVERTENCIA: La venta a crédito de {instance.total} excede el crédito disponible de {cliente.credito_disponible} para {cliente.nombre}")
                return
        
        # Actualizar la fecha de la última venta a crédito (opcional)
        # cliente.ultima_venta_credito = timezone.now()
        # cliente.save(update_fields=['ultima_venta_credito'])


@receiver(post_save, sender=CustomerPayment)
def update_sales_payment_status(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar un pago de cliente.
    Actualiza el estado de las ventas asociadas si el pago las cubre.
    """
    # Solo procesar si es un pago nuevo
    if created and instance.ventas.exists():
        with transaction.atomic():
            # Obtener todas las ventas asociadas a este pago
            ventas = instance.ventas.filter(pagado=False)
            
            # Calcular el total de las ventas no pagadas
            total_ventas = sum(venta.total for venta in ventas)
            
            # Si el pago cubre el total, marcar las ventas como pagadas
            if instance.monto >= total_ventas:
                for venta in ventas:
                    venta.pagado = True
                    venta.save(update_fields=['pagado'])
