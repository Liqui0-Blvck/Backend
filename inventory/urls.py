from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BoxTypeViewSet, FruitLotViewSet, StockReservationViewSet, ProductViewSet, GoodsReceptionViewSet, SupplierViewSet, ReceptionDetailViewSet, SupplierPaymentViewSet
from .concession_views import ConcessionSettlementViewSet, ConcessionSettlementDetailViewSet
from .maduracion_views import MaduracionPaltasView
from .views_detail import FruitLotDetailViewSet
from .product_views import ProductMovementViewSet

router = DefaultRouter()
router.register(r'boxtypes', BoxTypeViewSet, basename='boxtype')
router.register(r'fruits', FruitLotViewSet, basename='fruitlot')
router.register(r'reservations', StockReservationViewSet, basename='reservation')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-movements', ProductMovementViewSet, basename='product-movement')
router.register(r'goodsreceptions', GoodsReceptionViewSet, basename='goodsreception')
router.register(r'receptions', GoodsReceptionViewSet, basename='reception')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'receptiondetails', ReceptionDetailViewSet, basename='receptiondetail')
router.register(r'supplier-payments', SupplierPaymentViewSet, basename='supplierpayment')
router.register(r'concession-settlements', ConcessionSettlementViewSet, basename='concession-settlement')
router.register(r'concession-settlement-details', ConcessionSettlementDetailViewSet, basename='concession-settlement-detail')

# Crear instancia del ViewSet para el detalle de lote
fruitlot_detail = FruitLotDetailViewSet.as_view({
    'get': 'get_detail',
})

# Combinar las URLs del router con las URLs basadas en clases
urlpatterns = router.urls + [
    path('maduracion-paltas/', MaduracionPaltasView.as_view(), name='maduracion-paltas'),
    path('fruits/detalle/<str:uid>/', fruitlot_detail, name='fruitlot-detail'),
]
