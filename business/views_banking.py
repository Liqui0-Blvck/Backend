from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from .models_banking import BankAccount
from .serializers_banking import BankAccountSerializer
from .models import Business
from rest_framework.exceptions import ValidationError

class BankAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar las cuentas bancarias del negocio.
    """
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    lookup_field = 'id'
    queryset = BankAccount.objects.all()
    
    def get_queryset(self):
        """Filtrar por negocio del usuario autenticado"""
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return BankAccount.objects.none()
            
        # Filtrar por negocio del usuario
        return BankAccount.objects.filter(business=perfil.business)
    
    def perform_create(self, serializer):
        """Asignar automáticamente el negocio del usuario autenticado"""
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil is None:
            raise ValidationError("Usuario sin perfil asociado")
            
        serializer.save(business=perfil.business)
    
    @action(detail=False, methods=['GET'])
    def active_accounts(self, request):
        """Obtener solo las cuentas bancarias activas del negocio"""
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            return Response({"error": "Usuario sin perfil asociado"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        accounts = BankAccount.objects.filter(
            business=perfil.business,
            activa=True
        ).order_by('orden')
        
        serializer = self.get_serializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['PATCH'])
    def toggle_active(self, request, id=None):
        """Activar/desactivar una cuenta bancaria"""
        try:
            account = self.get_object()
            account.activa = not account.activa
            account.save()
            
            serializer = self.get_serializer(account)
            return Response(serializer.data)
        except BankAccount.DoesNotExist:
            return Response({"error": "Cuenta bancaria no encontrada"}, 
                           status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['PATCH'])
    def update_order(self, request, id=None):
        """Actualizar el orden de visualización de una cuenta bancaria"""
        try:
            account = self.get_object()
            new_order = request.data.get('orden')
            
            if new_order is None:
                return Response({"error": "Se requiere el parámetro 'orden'"}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            account.orden = int(new_order)
            account.save()
            
            serializer = self.get_serializer(account)
            return Response(serializer.data)
        except BankAccount.DoesNotExist:
            return Response({"error": "Cuenta bancaria no encontrada"}, 
                           status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error": "El valor de 'orden' debe ser un número entero"}, 
                           status=status.HTTP_400_BAD_REQUEST)
