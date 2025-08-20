from django.urls import path
from rest_framework.routers import DefaultRouter
from .views_settlements import ConcessionSettlementViewSet

router = DefaultRouter()
router.register('', ConcessionSettlementViewSet)

urlpatterns = router.urls
