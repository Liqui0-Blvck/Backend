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
    logger.info(f"Signal pre_save activado para SalePending {instance.pk} - Estado: {instance.estado}")
    
    # Verificar si es una instancia existente (no nueva)
    if instance.pk:
        try:
            # Obtener el estado anterior
            old_instance = SalePending.objects.get(pk=instance.pk)
            logger.info(f"Estado anterior: {old_instance.estado}, Estado nuevo: {instance.estado}")
            
            # Si el estado cambió a 'confirmada'
            if old_instance.estado != 'confirmada' and instance.estado == 'confirmada':
                with transaction.atomic():
                    # Determinar si el producto es tipo palta u otro
                    es_palta = instance.lote.producto and instance.lote.producto.tipo_producto == 'palta'
                    
                    # Calcular el total si no está definido
                    if not instance.total:
                        if es_palta and instance.precio_kg:
                            total_calculado = instance.precio_kg * instance.cantidad_kg
                        elif not es_palta and hasattr(instance, 'precio_unidad'):
                            total_calculado = instance.precio_unidad * instance.cantidad_unidades
                        else:
                            total_calculado = Decimal('0')
                    else:
                        total_calculado = instance.total
                    
                    # Crear una nueva venta a partir de la venta pendiente
                    sale = Sale(
                        uid=uuid.uuid4(),  # Generar nuevo UUID
                        codigo_venta=instance.codigo_venta,  # Transferir el código de venta
                        lote=instance.lote,
                        cliente=instance.cliente,
                        vendedor=instance.vendedor,
                        # Campos para productos tipo palta
                        peso_vendido=instance.cantidad_kg if es_palta else 0,
                        precio_kg=instance.precio_kg or 0 if es_palta else 0,
                        # Campos para productos tipo otro
                        unidades_vendidas=instance.cantidad_unidades if not es_palta else 0,
                        precio_unidad=getattr(instance, 'precio_unidad', 0) if not es_palta else 0,
                        # Campos comunes
                        cajas_vendidas=instance.cantidad_cajas,
                        total=total_calculado,
                        metodo_pago=instance.metodo_pago or 'efectivo',
                        comprobante=instance.comprobante,
                        business=instance.business,
                        fecha_vencimiento=instance.fecha_vencimiento or (timezone.now() + timezone.timedelta(days=30)),
                        pagado=False,  # Por defecto, la venta no está pagada
                        saldo_pendiente=total_calculado,
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
    Actualiza el inventario del lote de fruta, descontando las cajas y kilos/unidades vendidos
    según el tipo de producto (palta o otro).
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
                    
                    # Descontar cajas vendidas (común para ambos tipos de productos)
                    if instance.cajas_vendidas > 0:
                        lote.cantidad_cajas = max(0, lote.cantidad_cajas - instance.cajas_vendidas)
                    
                    # Actualizar inventario según tipo de producto
                    if lote.producto and lote.producto.tipo_producto == 'palta':
                        # Para productos tipo palta: actualizar por peso
                        if instance.peso_vendido > Decimal('0'):
                            # Actualizamos directamente el peso_neto
                            if lote.peso_neto is not None:
                                lote.peso_neto = max(Decimal('0'), lote.peso_neto - instance.peso_vendido)
                        
                        # Actualizar estado del lote según disponibilidad de peso y cajas
                        if lote.cantidad_cajas == 0 and (lote.peso_neto is None or lote.peso_neto <= Decimal('0')):
                            lote.estado_lote = 'agotado'
                            # Guardar cambios en el lote incluyendo el estado_lote
                            lote.save(update_fields=['cantidad_cajas', 'peso_neto', 'estado_lote', 'updated_at'])
                            logger.info(f"Lote {lote.uid} marcado como agotado: cajas={lote.cantidad_cajas}, peso_neto={lote.peso_neto}")
                        else:
                            # Guardar cambios en el lote sin modificar estado_lote
                            lote.save(update_fields=['cantidad_cajas', 'peso_neto', 'updated_at'])
                        logger.info(f"Inventario actualizado (palta): Lote {lote.uid} - Disponible: {lote.peso_neto}kg/{lote.cantidad_cajas}cajas")
                    else:
                        # Para productos tipo otro: actualizar por unidades
                        if hasattr(instance, 'unidades_vendidas') and instance.unidades_vendidas > 0:
                            lote.cantidad_unidades = max(0, lote.cantidad_unidades - instance.unidades_vendidas)
                            lote.unidades_reservadas = max(0, lote.unidades_reservadas - instance.unidades_vendidas)
                        
                        # Actualizar estado del lote según disponibilidad de unidades y cajas
                        if lote.cantidad_cajas == 0 and lote.cantidad_unidades == 0:
                            lote.estado_lote = 'agotado'
                            # Guardar cambios en el lote incluyendo el estado_lote
                            lote.save(update_fields=['cantidad_cajas', 'cantidad_unidades', 'unidades_reservadas', 'estado_lote', 'updated_at'])
                            logger.info(f"Lote {lote.uid} marcado como agotado: cajas={lote.cantidad_cajas}, unidades={lote.cantidad_unidades}")
                        else:
                            # Guardar cambios en el lote sin modificar estado_lote
                            lote.save(update_fields=['cantidad_cajas', 'cantidad_unidades', 'unidades_reservadas', 'updated_at'])
                        logger.info(f"Inventario actualizado (otro): Lote {lote.uid} - Disponible: {lote.cantidad_unidades}unidades/{lote.cantidad_cajas}cajas")
        
        except Exception as e:
            logger.error(f"Error al actualizar inventario para venta {instance.codigo_venta or instance.id}: {str(e)}")
            # Registrar más detalles para depuración
            import traceback
            logger.error(traceback.format_exc())



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

