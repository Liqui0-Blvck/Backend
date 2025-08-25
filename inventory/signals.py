from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from .models import StockReservation, FruitLot

import logging

logger = logging.getLogger(__name__)

@receiver([post_save, post_delete], sender=StockReservation)
def update_lot_status_on_reservation(sender, instance, **kwargs):
    """
    Actualiza el estado de un FruitLot basado en sus reservas de stock.
    Solo actualiza el estado, no modifica la cantidad de cajas.
    """
    try:
        lote = instance.lote
        if not lote:
            return

        # Calcular el total de cajas reservadas en proceso
        total_cajas_reservadas = StockReservation.objects.filter(
            lote=lote, estado='en_proceso'
        ).aggregate(total=Sum('cajas_reservadas'))['total'] or 0

        # Calcular stock disponible (solo para fines informativos y de estado)
        stock_disponible_cajas = lote.cantidad_cajas - total_cajas_reservadas
        
        logger.info(f"Lote {lote.uid}: total_cajas={lote.cantidad_cajas}, reservadas={total_cajas_reservadas}, disponibles={stock_disponible_cajas}")

        # IMPORTANTE: Solo actualizamos el estado del lote, NO modificamos la cantidad de cajas
        # El estado solo es informativo y no debe afectar la cantidad real de cajas
        if stock_disponible_cajas <= 0 and lote.estado_lote == 'activo':
            # Solo actualizamos el estado, no la cantidad
            lote.estado_lote = 'reservado'
            lote.save(update_fields=['estado_lote'])
            logger.info(f"Lote {lote.uid} marcado como 'reservado' debido a reservas. Stock disponible: {stock_disponible_cajas}")
        elif stock_disponible_cajas > 0 and lote.estado_lote == 'reservado':
            # Esta condición es importante si una reserva se cancela y el lote vuelve a tener stock
            lote.estado_lote = 'activo'
            lote.save(update_fields=['estado_lote'])
            logger.info(f"Lote {lote.uid} revertido a 'activo'. Stock disponible: {stock_disponible_cajas}")
        
        # El estado 'agotado' solo debe ser establecido cuando realmente se vende el producto
        # y se actualiza la cantidad de cajas a 0 en el modelo SaleItem

    except Exception as e:
        logger.error(f"Error en la señal update_lot_status_on_reservation para la reserva {instance.uid}: {str(e)}")
