from rest_framework.routers import DefaultRouter
from .views import ShiftViewSet, ShiftExpenseViewSet

router = DefaultRouter()
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'shift-expenses', ShiftExpenseViewSet, basename='shift-expense')

urlpatterns = router.urls
