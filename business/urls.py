from rest_framework.routers import DefaultRouter
from .views import BusinessViewSet, BusinessConfigViewSet

router = DefaultRouter()
router.register(r'businesses', BusinessViewSet, basename='business')
router.register(r'config', BusinessConfigViewSet, basename='business-config')

urlpatterns = router.urls
