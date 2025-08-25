"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

# Configurar Django primero
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Inicializar la aplicación ASGI de Django
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# Importar el resto de los módulos después de que Django esté configurado
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import notifications.routing
import inventory.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                notifications.routing.websocket_urlpatterns +
                inventory.routing.websocket_urlpatterns
            )
        )
    ),
})
