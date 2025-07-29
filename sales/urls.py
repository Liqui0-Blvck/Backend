from django.urls import path, include
from rest_framework import routers
from .views import SaleViewSet, SalePendingViewSet, CustomerViewSet, CustomerPaymentViewSet, actualizar_credito_cliente

router = routers.DefaultRouter()
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'pending', SalePendingViewSet)
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'customer-payments', CustomerPaymentViewSet, basename='customer-payment')

urlpatterns = [
    # Incluir todas las rutas generadas por el router
    path('', include(router.urls)),
    
    # Ruta específica para actualizar crédito
    path('customers/<str:uid>/actualizar-credito/', actualizar_credito_cliente, name='actualizar-credito-cliente'),
]
