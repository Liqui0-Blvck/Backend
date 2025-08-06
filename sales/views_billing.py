from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from .models_billing import BillingInfo
from .serializers_billing import BillingInfoSerializer
from .models import Customer

class BillingInfoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar la información de facturación de los clientes.
    """
    serializer_class = BillingInfoSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'id'
    queryset = BillingInfo.objects.all()
    
    def get_queryset(self):
        """Filtrar por negocio del usuario autenticado"""
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return BillingInfo.objects.none()
            
        # Filtrar por clientes que pertenecen al negocio del usuario
        return BillingInfo.objects.filter(cliente__business=perfil.business)
    
    def perform_create(self, serializer):
        """Verificar que el cliente pertenece al negocio del usuario"""
        cliente_id = self.request.data.get('cliente')
        try:
            cliente = Customer.objects.get(id=cliente_id)
            perfil = getattr(self.request.user, 'perfil', None)
            
            if perfil is None or cliente.business != perfil.business:
                raise ValidationError("El cliente no pertenece a su negocio")
                
            # Verificar si ya existe información de facturación para este cliente
            if BillingInfo.objects.filter(cliente=cliente).exists():
                raise ValidationError("Este cliente ya tiene información de facturación. Use PUT para actualizarla.")
                
            serializer.save()
        except Customer.DoesNotExist:
            raise ValidationError("Cliente no encontrado")
    
    @action(detail=False, methods=['GET', 'PUT'])
    def by_customer(self, request):
        """Obtener o actualizar la información de facturación por cliente_uid"""
        cliente_uid = request.query_params.get('cliente_uid')
        if not cliente_uid:
            return Response({"error": "Se requiere el parámetro cliente_uid"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            cliente = Customer.objects.get(uid=cliente_uid)
            
            # Verificar permisos
            perfil = getattr(request.user, 'perfil', None)
            if perfil is None or cliente.business != perfil.business:
                return Response({"error": "No tiene acceso a este cliente"}, 
                               status=status.HTTP_403_FORBIDDEN)
            
            # Obtener o crear la información de facturación
            billing_info, created = BillingInfo.objects.get_or_create(
                cliente=cliente,
                defaults={
                    'razon_social': cliente.nombre,
                    'rut_facturacion': cliente.rut
                }
            )
            
            if request.method == 'PUT':
                serializer = self.get_serializer(billing_info, data=request.data)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                # GET request
                serializer = self.get_serializer(billing_info)
                return Response(serializer.data)
                
        except Customer.DoesNotExist:
            return Response({"error": "Cliente no encontrado"}, 
                           status=status.HTTP_404_NOT_FOUND)
