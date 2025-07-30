from django.db.models.signals import post_save, m2m_changed, pre_save
from django.dispatch import receiver
from .models import Sale, CustomerPayment, Customer, SalePending
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal
from inventory.models import FruitLot, StockReservation
import logging
import uuid

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=SalePending)
def convert_pending_to_sale(sender, instance, **kwargs):
    """
    Signal que se activa antes de guardar una venta pendiente.
    Si el estado cambia a 'confirmada', crea una venta (Sale) a partir de la venta pendiente.
    """
    # Verificar si es una instancia existente (no nueva)
    if instance.pk:
        try:
            # Obtener el estado anterior
            old_instance = SalePending.objects.get(pk=instance.pk)
            
            # Si el estado cambió a 'confirmada'
            if old_instance.estado != 'confirmada' and instance.estado == 'confirmada':
                with transaction.atomic():
                    # Crear una nueva venta a partir de la venta pendiente
                    sale = Sale(
                        uid=uuid.uuid4(),  # Generar nuevo UUID
                        lote=instance.lote,
                        cliente=instance.cliente,
                        vendedor=instance.vendedor,
                        peso_vendido=instance.cantidad_kg,
                        cajas_vendidas=instance.cantidad_cajas,
                        precio_kg=instance.precio_kg or 0,
                        total=instance.total or (instance.precio_kg * instance.cantidad_kg if instance.precio_kg else 0),
                        metodo_pago=instance.metodo_pago or 'efectivo',
                        comprobante=instance.comprobante,
                        business=instance.business,
                        fecha_vencimiento=instance.fecha_vencimiento or (timezone.now() + timezone.timedelta(days=30)),
                        pagado=False,  # Por defecto, la venta no está pagada
                        saldo_pendiente=instance.total or (instance.precio_kg * instance.cantidad_kg if instance.precio_kg else 0),
                        estado_pago='pendiente'
                    )
                    sale.save()
                    
                    # Actualizar la reserva de stock a 'confirmada'
                    StockReservation.objects.filter(
                        lote=instance.lote,
                        cantidad_kg=instance.cantidad_kg,
                        cantidad_cajas=instance.cantidad_cajas,
                        estado='en_proceso'
                    ).update(estado='confirmada')
                    
                    logger.info(f"Venta pendiente {instance.pk} convertida a venta confirmada {sale.pk}")
        except SalePending.DoesNotExist:
            # Es una nueva instancia, no hacer nada
            pass
        except Exception as e:
            logger.error(f"Error al convertir venta pendiente a confirmada: {str(e)}")
            # No propagar la excepción para evitar bloquear el guardado

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


@receiver(post_save, sender=Sale)
def update_fruit_lot_inventory(sender, instance, created, **kwargs):
    """
    Señal que se activa después de guardar una venta.
    Actualiza el inventario del lote de fruta, descontando las cajas y kilos vendidos.
    """
    # Solo procesar si es una venta nueva (creación) o si se está actualizando una venta existente
    # pero solo si no se está actualizando desde otra señal para evitar recursión
    if kwargs.get('update_fields') is None or 'updated_at' not in kwargs.get('update_fields', []):
        try:
            with transaction.atomic():
                # Obtener el lote de fruta asociado a la venta
                lote = instance.lote
                
                # Verificar que el lote existe
                if not lote:
                    logger.error(f"No se encontró el lote asociado a la venta {instance.codigo_venta or instance.id}")
                    return
                
                # Si es una venta nueva, descontar del inventario
                if created:
                    logger.info(f"Actualizando inventario para lote {lote.uid} - Venta: {instance.codigo_venta}")
                    
                    # Descontar cajas vendidas
                    if instance.cajas_vendidas > 0:
                        lote.cajas_disponibles = max(0, lote.cajas_disponibles - instance.cajas_vendidas)
                    
                    # Descontar peso vendido
                    if instance.peso_vendido > Decimal('0'):
                        lote.peso_neto_disponible = max(Decimal('0'), lote.peso_neto_disponible - instance.peso_vendido)
                        
                        # Actualizar porcentaje disponible
                        if lote.peso_neto > 0:
                            lote.porcentaje_disponible = (lote.peso_neto_disponible / lote.peso_neto) * 100
                        else:
                            lote.porcentaje_disponible = 0
                    
                    # Actualizar estado del lote según disponibilidad
                    if lote.peso_neto_disponible <= 0 or lote.porcentaje_disponible <= 0:
                        lote.estado_lote = 'agotado'
                    
                    # Guardar cambios en el lote
                    lote.save(update_fields=['cajas_disponibles', 'peso_neto_disponible', 'porcentaje_disponible', 'estado_lote', 'updated_at'])
                    logger.info(f"Inventario actualizado: Lote {lote.uid} - Disponible: {lote.peso_neto_disponible}kg/{lote.cajas_disponibles}cajas")
        
        except Exception as e:
            logger.error(f"Error al actualizar inventario para venta {instance.codigo_venta or instance.id}: {str(e)}")



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

