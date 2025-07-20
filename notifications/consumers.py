import json
import logging
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

logger = logging.getLogger(__name__)

CustomUser = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        try:
            # 1. Autenticar usuario
            user = await self.get_user_from_scope()
            if not user or isinstance(user, AnonymousUser):
                logger.warning("WebSocket - Conexión rechazada: Usuario no autenticado.")
                await self.close()
                return
            self.scope['user'] = user

            # 2. Aceptar la conexión
            await self.accept()
            logger.info(f"WebSocket - Conexión aceptada para {user.email}")

            # 3. Manejar lógica de perfiles y grupos
            # Superusuario sin perfil: solo se une a su canal personal
            if user.is_superuser and (not hasattr(user, 'perfil') or not user.perfil):
                logger.info(f"WebSocket - Superusuario {user.email} conectado sin perfil de negocio.")
                self.user_group_name = f'notifications_user_{user.id}'
                await self.channel_layer.group_add(self.user_group_name, self.channel_name)
                logger.info(f"  -> Unido al grupo personal: {self.user_group_name}")
                return

            # Usuario normal debe tener perfil
            if not hasattr(user, 'perfil') or not user.perfil:
                logger.error(f"WebSocket - Usuario {user.email} no tiene perfil. Desconectando.")
                await self.close()
                return

            # 4. Verificar pertenencia al negocio desde la URL
            business_id_str = self.scope['url_route']['kwargs'].get('business_id')
            if not business_id_str:
                logger.error("WebSocket - No se proporcionó business_id en la URL. Desconectando.")
                await self.close()
                return
            
            self.business_id = int(business_id_str)
            is_member = await self.user_belongs_to_business(user, self.business_id)
            if not is_member:
                logger.warning(f"WebSocket - Usuario {user.email} no pertenece al negocio {self.business_id}. Desconectando.")
                await self.close()
                return

            # 5. Unir a los grupos correspondientes
            self.user_group_name = f'notifications_user_{user.id}'
            self.business_group_name = f'notifications_business_{self.business_id}'
            
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)
            logger.info(f"  -> Unido al grupo personal: {self.user_group_name}")
            
            await self.channel_layer.group_add(self.business_group_name, self.channel_name)
            logger.info(f"  -> Unido al grupo de negocio: {self.business_group_name}")

        except Exception as e:
            logger.error(f"WebSocket - Error fatal en la conexión: {e}")
            logger.error(traceback.format_exc())
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'business_group_name'):
            await self.channel_layer.group_discard(
                self.business_group_name,
                self.channel_name
            )
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        logger.info(f"WebSocket - Conexión cerrada con código: {close_code}")

    async def receive(self, text_data):
        logger.info(f"WebSocket - Mensaje recibido: {text_data}")
        pass

    async def notification_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))
        logger.info(f"WebSocket - Notificación enviada al cliente: {self.scope['user'].email}")

    @database_sync_to_async
    def get_user_from_scope(self):
        """
        Obtiene el usuario desde el scope, priorizando el token JWT de la aplicación
        y luego recurriendo a la cookie de sesión de Django.
        """
        # 1. Priorizar la autenticación por token JWT desde las cookies
        access_token = self.scope['cookies'].get('accessToken')
        if access_token:
            try:
                validated_token = AccessToken(access_token)
                user_id = validated_token['user_id']
                user = CustomUser.objects.select_related('perfil').get(pk=user_id)
                logger.info(f"WebSocket - Usuario autenticado por token JWT: {user.email}")
                return user
            except (TokenError, CustomUser.DoesNotExist) as e:
                logger.warning(f"WebSocket - Falló la autenticación con token JWT: {e}")
                # No retornamos None aquí, para dar paso a la autenticación por sesión

        # 2. Si el token falla o no existe, intentar con el usuario de la sesión
        user = self.scope.get('user')
        if user and not user.is_anonymous:
            logger.info(f"WebSocket - Usuario autenticado por sesión (fallback): {user.email}")
            try:
                # Asegurarse de que el perfil está cargado
                if hasattr(user, 'perfil'):
                    return user
                return CustomUser.objects.select_related('perfil').get(pk=user.pk)
            except CustomUser.DoesNotExist:
                pass # Dejar que el flujo continúe para el rechazo final
        
        logger.warning("WebSocket - Conexión rechazada: Usuario no autenticado.")
        return None

    @database_sync_to_async
    def user_belongs_to_business(self, user, business_id):
        if not hasattr(user, 'perfil') or not user.perfil:
            return False
        return user.perfil.business_id == business_id
