from django.db.models.signals import post_save, m2m_changed, pre_save
from django.dispatch import receiver
from .models import Sale, CustomerPayment, Customer, SalePending, SaleItem, SalePendingItem
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal
from inventory.models import FruitLot, StockReservation
import logging
import uuid

logger = logging.getLogger(__name__)

# NOTA: El signal pre_save para SalePending ha sido eliminado
# La conversión de venta pendiente a venta directa ahora se maneja
# en el método update del serializador SalePendingSerializer

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
def update_customer_balance(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar un pago de cliente.
    Actualiza el saldo del cliente y su crédito disponible.
    """
    if instance.cliente:
        logger.info(f"Actualizando saldo para cliente {instance.cliente.nombre} tras pago de ${instance.monto}")
        # No es necesario hacer nada más aquí, ya que el saldo_actual y credito_disponible
        # son propiedades calculadas que consultan los pagos y ventas en tiempo real


@receiver(post_save, sender=SaleItem)
def update_fruit_lot_inventory(sender, instance, created, **kwargs):
    """
    Deshabilitado: SaleItem.save() ya actualiza el inventario del Lote/Bin con deltas.
    Mantener este signal haciendo early-return evita descuentos duplicados (p.ej., 2 cajas
    en vez de 1 cuando se vende 1 caja) que ocurrían al ejecutar lógica en ambos lugares.
    """
    # No hacer nada aquí para evitar doble descuento
    return


@receiver(m2m_changed, sender=CustomerPayment.ventas.through)
def update_sales_payment_status(sender, instance, action, pk_set, **kwargs):
    """
    Señal que se activa cuando se asocian ventas a un pago.
    Actualiza el estado de las ventas asociadas si el pago las cubre.
    """
    # Solo procesar cuando se añaden ventas al pago
    if action == 'post_add' and pk_set:
        logger.info(f"Procesando pago {instance.uid} para {len(pk_set)} ventas")
        
        with transaction.atomic():
            # Obtener todas las ventas asociadas a este pago que no están pagadas
            ventas = instance.ventas.filter(pagado=False)
            
            if not ventas.exists():
                logger.info("No hay ventas pendientes asociadas a este pago")
                return
                
            # Calcular el total de las ventas no pagadas
            total_ventas = sum(venta.total for venta in ventas)
            logger.info(f"Total de ventas pendientes: ${total_ventas}, monto del pago: ${instance.monto}")
            
            # Si el pago cubre el total, marcar las ventas como pagadas
            if instance.monto >= total_ventas:
                for venta in ventas:
                    venta.pagado = True
                    venta.save(update_fields=['pagado'])
                logger.info(f"Se marcaron {ventas.count()} ventas como pagadas")
            else:
                logger.info(f"El pago no cubre el total de las ventas pendientes (${total_ventas})")
                
            # Actualizar el cliente para reflejar el nuevo saldo
            if instance.cliente:
                # Forzar una actualización del cliente para refrescar las propiedades calculadas
                instance.cliente.save(update_fields=['updated_at'])
                logger.info(f"Saldo actualizado para cliente {instance.cliente.nombre}: ${instance.cliente.saldo_actual}, disponible: ${instance.cliente.credito_disponible}")

