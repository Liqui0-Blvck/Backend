from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/(?P<business_id>\d+)/$', consumers.NotificationConsumer.as_asgi()),
]
