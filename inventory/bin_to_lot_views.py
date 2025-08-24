from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .bin_to_lot_serializers import BinToLotSerializer, BinToLotResponseSerializer
from .models import FruitBin, FruitLot
from accounts.models import Perfil
from rest_framework.exceptions import ValidationError

class BinToLotTransformView(APIView):
    """
    Vista para transformar bins de fruta a lotes (pallets)
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Transforma bins de fruta a un nuevo lote (pallet)
        """
        # Obtener el negocio del usuario
        user = request.user
        business = None
        
        # Verificar si el usuario tiene un negocio directamente asociado
        if hasattr(user, 'business') and user.business:
            business = user.business
        else:
            # Buscar el negocio en el perfil del usuario
            try:
                perfil = Perfil.objects.get(user=user)
                if perfil.business:
                    business = perfil.business
            except Perfil.DoesNotExist:
                pass
        
        if not business:
            return Response(
                {"detail": "Usuario no tiene un negocio asociado"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar y procesar los datos de entrada
        serializer = BinToLotSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Crear el nuevo lote
                nuevo_lote = serializer.save()
                
                # Preparar la respuesta
                response_serializer = BinToLotResponseSerializer(nuevo_lote)
                return Response(
                    {
                        "message": "Transformación exitosa",
                        "lote": response_serializer.data,
                        "bins_transformados": len(serializer.validated_data['bin_ids'])
                    }, 
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                # Manejar errores durante la creación
                return Response(
                    {"detail": f"Error al transformar bins: {str(e)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Devolver errores de validación
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
