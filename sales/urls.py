from django.urls import path, include
from rest_framework import routers
from .views import (
    SaleViewSet, SalePendingViewSet, CustomerViewSet, 
    actualizar_credito_cliente, ventas_cliente, pagos_cliente, 
    historial_completo_cliente, registrar_pago_cliente, 
    # informacion_deuda_cliente,
    ordenes_pendientes_cliente
)

router = routers.DefaultRouter()
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'pending', SalePendingViewSet)
router.register(r'customers', CustomerViewSet, basename='customer')

urlpatterns = [
    # Incluir todas las rutas generadas por el router
    path('', include(router.urls)),
    
    # Rutas específicas para clientes
    path('customers/<str:uid>/actualizar-credito/', actualizar_credito_cliente, name='actualizar-credito-cliente'),
    path('customers/<str:uid>/ventas/', ventas_cliente, name='ventas-cliente'),
    path('customers/<str:uid>/pagos/', pagos_cliente, name='pagos-cliente'),
    path('customers/<str:uid>/historial-completo/', historial_completo_cliente, name='historial-completo-cliente'),
    path('customers/<str:uid>/registrar-pago/', registrar_pago_cliente, name='registrar-pago-cliente'),
    # path('customers/<str:uid>/deuda/', informacion_deuda_cliente, name='informacion-deuda-cliente'),
    path('customers/<str:uid>/ordenes-pendientes/', ordenes_pendientes_cliente, name='ordenes-pendientes-cliente'),
]
