from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/stock/(?P<lote_id>\d+)/$", consumers.StockConsumer.as_asgi()),
]
