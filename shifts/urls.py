from rest_framework.routers import DefaultRouter
from .views import ShiftViewSet, ShiftExpenseViewSet, ShiftClosingViewSet, BoxRefillViewSet

router = DefaultRouter()
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'shift-expenses', ShiftExpenseViewSet, basename='shift-expense')
router.register(r'shift-closings', ShiftClosingViewSet, basename='shift-closing')
router.register(r'box-refills', BoxRefillViewSet, basename='box-refill')

urlpatterns = router.urls
