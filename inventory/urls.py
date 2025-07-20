from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BoxTypeViewSet, FruitLotViewSet, StockReservationViewSet, ProductViewSet, GoodsReceptionViewSet, SupplierViewSet, ReceptionDetailViewSet
from .maduracion_views import MaduracionPaltasView

router = DefaultRouter()
router.register(r'boxtypes', BoxTypeViewSet, basename='boxtype')
router.register(r'fruits', FruitLotViewSet, basename='fruitlot')
router.register(r'reservations', StockReservationViewSet, basename='reservation')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'goodsreceptions', GoodsReceptionViewSet, basename='goodsreception')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'receptiondetails', ReceptionDetailViewSet, basename='receptiondetail')

# Combinar las URLs del router con las URLs basadas en clases
urlpatterns = router.urls + [
    path('maduracion-paltas/', MaduracionPaltasView.as_view(), name='maduracion-paltas'),
]
