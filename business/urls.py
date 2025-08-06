from rest_framework.routers import DefaultRouter
from .views import BusinessViewSet, BusinessConfigViewSet
from .views_banking import BankAccountViewSet

router = DefaultRouter()
router.register(r'businesses', BusinessViewSet, basename='business')
router.register(r'config', BusinessConfigViewSet, basename='business-config')
router.register(r'bank-accounts', BankAccountViewSet, basename='bank-account')

urlpatterns = router.urls
