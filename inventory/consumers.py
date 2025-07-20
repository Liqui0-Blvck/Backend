import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

class StockConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lote_id = self.scope['url_route']['kwargs']['lote_id']
        self.group_name = f'stock_{self.lote_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_stock_update()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Solo lectura, no procesamos mensajes del cliente
        pass

    async def stock_update(self, event):
        await self.send_stock_update()

    async def send_stock_update(self):
        from .models import FruitLot, StockReservation
        lote = await sync_to_async(FruitLot.objects.get)(id=self.lote_id)
        reservas = await sync_to_async(list)(StockReservation.objects.filter(lote_id=self.lote_id, estado="en_proceso"))
        total_reservado = sum([float(r.cantidad_kg) for r in reservas])
        await self.send(text_data=json.dumps({
            "lote_id": self.lote_id,
            "stock_real": float(lote.peso_neto),
            "stock_reservado": total_reservado,
            "stock_disponible": float(lote.peso_neto) - total_reservado
        }))
