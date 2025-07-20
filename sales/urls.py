from rest_framework import routers
from .views import SaleViewSet, SalePendingViewSet, CustomerViewSet

router = routers.DefaultRouter()
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'pending', SalePendingViewSet)
router.register(r'customers', CustomerViewSet, basename='customer')

urlpatterns = router.urls
