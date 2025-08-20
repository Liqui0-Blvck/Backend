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
    """
    try:
        lote = instance.lote
        if not lote:
            return

        # Calcular el total de cajas reservadas en proceso
        total_cajas_reservadas = StockReservation.objects.filter(
            lote=lote, estado='en_proceso'
        ).aggregate(total=Sum('cajas_reservadas'))['total'] or 0

        stock_disponible_cajas = lote.cantidad_cajas - total_cajas_reservadas

        # Actualizar el estado del lote basado en la disponibilidad real
        if stock_disponible_cajas <= 0 and lote.estado_lote == 'activo':
            lote.estado_lote = 'agotado'
            lote.save()
            logger.info(f"Lote {lote.uid} marcado como 'agotado' debido a reservas. Stock disponible: {stock_disponible_cajas}")
        elif stock_disponible_cajas > 0 and lote.estado_lote == 'agotado':
            # Esta condición es importante si una reserva se cancela y el lote vuelve a tener stock
            lote.estado_lote = 'activo'
            lote.save()
            logger.info(f"Lote {lote.uid} revertido a 'activo'. Stock disponible: {stock_disponible_cajas}")

    except Exception as e:
        logger.error(f"Error en la señal update_lot_status_on_reservation para la reserva {instance.uid}: {str(e)}")
