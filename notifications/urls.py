from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet
from .webhook_views import WebhookSubscriptionViewSet

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')
router.register(r'webhooks', WebhookSubscriptionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
