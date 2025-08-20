from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import SupplierPaymentViewSet

router = DefaultRouter()
router.register('', SupplierPaymentViewSet)

urlpatterns = router.urls
