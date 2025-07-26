from rest_framework import viewsets, status
from .models import BoxType, FruitLot, StockReservation, Product, GoodsReception, Supplier, ReceptionDetail
from .serializers import BoxTypeSerializer, FruitLotSerializer, StockReservationSerializer, ProductSerializer, GoodsReceptionSerializer, SupplierSerializer, ReceptionDetailSerializer
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness
from accounts.models import CustomUser
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
import json

class RolePermissionMixin:
    def get_permissions(self):
        user = self.request.user
        perms = super().get_permissions()
        # Puedes agregar lógica granular aquí por rol
        # Ejemplo: solo admin/supervisor pueden modificar, vendedores solo crear, visualizadores solo leer
        return perms

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        
        if perfil is None:
            return qs.none()
            
        # Visualizador solo puede ver, vendedor solo los de su empresa, admin/supervisor todo
        if user.groups.filter(name='Visualizador').exists():
            return qs.filter(business=perfil.business)
        elif user.groups.filter(name='Vendedor').exists():
            return qs.filter(business=perfil.business)
        elif user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
            return qs.filter(business=perfil.business)
        return qs.none()

class BoxTypeViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = BoxTypeSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = BoxType.objects.all()
    lookup_field = 'uid'
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
    
    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)

class FruitLotViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = FruitLotSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = FruitLot.objects.all()
    lookup_field = 'uid'

    def get_queryset(self):
        qs = super().get_queryset()
        # Verificar si hay un filtro específico por estado_lote
        estado_lote = self.request.query_params.get('estado_lote', None)
        
        # Si se solicita específicamente un estado, aplicar ese filtro
        if estado_lote is not None:
            return qs.filter(estado_lote=estado_lote)
        
        # Si no hay filtro específico, ocultar los lotes agotados por defecto
        return qs.exclude(estado_lote='agotado')

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)

    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
        
    @action(detail=True, methods=['post'], url_path='update-suggested-prices')
    def update_suggested_prices(self, request, uid=None):
        """Actualiza los precios sugeridos (min/max) de un lote de fruta"""
        from .serializers_update import FruitLotSuggestedPriceUpdateSerializer
        
        lote = self.get_object()
        serializer = FruitLotSuggestedPriceUpdateSerializer(lote, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Precios sugeridos actualizados correctamente',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'status': 'error',
            'message': 'Error al actualizar precios sugeridos',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='update-maturation')
    def update_maturation(self, request, uid=None):
        """Actualiza el estado de maduración de un lote de fruta"""
        from .serializers_update import FruitLotMaturationUpdateSerializer
        from .models import MadurationHistory
        
        lote = self.get_object()
        estado_anterior = lote.estado_maduracion
        serializer = FruitLotMaturationUpdateSerializer(lote, data=request.data, partial=True)
        
        if serializer.is_valid():
            # Guardar el lote actualizado
            lote_actualizado = serializer.save()
            
            # Verificar si el estado de maduración cambió
            if 'estado_maduracion' in request.data and lote_actualizado.estado_maduracion != estado_anterior:
                # Registrar el cambio en el historial de maduración
                MadurationHistory.objects.create(
                    lote=lote_actualizado,
                    estado_maduracion=lote_actualizado.estado_maduracion
                )
            
            return Response({
                'status': 'success',
                'message': 'Estado de maduración actualizado correctamente',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'status': 'error',
            'message': 'Error al actualizar estado de maduración',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class ProductViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = Product.objects.all()
    lookup_field = 'uid'
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({'request': self.request})
        return context
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
    
    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)


class StockReservationViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = StockReservationSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = StockReservation.objects.all()
    lookup_field = 'uid'

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
            
        reserva = serializer.save(usuario=user, business=perfil.business)
        self.notify_ws(reserva.lote_id)

    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
            
        reserva = serializer.save(business=perfil.business)
        self.notify_ws(reserva.lote_id)

    def perform_destroy(self, instance):
        lote_id = instance.lote_id
        instance.delete()
        self.notify_ws(lote_id)

    def notify_ws(self, lote_id):
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            reservas = StockReservation.objects.filter(lote_id=lote_id, estado="en_proceso")
            total_reservado = sum([float(r.cantidad_kg) for r in reservas])
            async_to_sync(channel_layer.group_send)(
                f"stock_{lote_id}",
                {
                    "type": "stock_update",
                    "message": json.dumps({
                        "lote_id": lote_id,
                        "reservas_en_proceso": total_reservado
                    })
                }
            )
        except Exception as e:
            pass

class GoodsReceptionViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = GoodsReceptionSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = GoodsReception.objects.all()
    lookup_field = 'uid'
    
    @action(detail=False, methods=['post'])
    def crear_recepcion(self, request):
        import json
        from rest_framework.response import Response
        from rest_framework import status
        
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado para el usuario'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extraer datos básicos
        data = request.data.copy()
        
        # Manejar detalles si vienen como string JSON (aceptar tanto 'detalles' como 'detalles_json')
        detalles_str = data.get('detalles') or data.get('detalles_json')
        if detalles_str and isinstance(detalles_str, str):
            try:
                detalles = json.loads(detalles_str)
            except json.JSONDecodeError:
                return Response({'detalles': 'Formato JSON inválido'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Si no hay string JSON, buscar si hay una lista directamente
            detalles = data.get('detalles') or data.get('detalles_json') or []
        
        # Manejar proveedor por uid
        proveedor_uid = data.get('proveedor')
        if proveedor_uid and not str(proveedor_uid).isdigit():
            from inventory.models import Supplier
            try:
                proveedor = Supplier.objects.get(uid=proveedor_uid)
                data['proveedor'] = proveedor.id
            except Supplier.DoesNotExist:
                return Response({'proveedor': 'Proveedor no encontrado'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear la recepción
        try:
            # Eliminar detalles del diccionario principal
            if 'detalles' in data:
                del data['detalles']
            if 'detalles_json' in data:
                del data['detalles_json']
                
            # Asignar usuario y negocio
            data['recibido_por'] = user.id
            data['business'] = perfil.business.id
            
            # Crear recepción
            recepcion_serializer = self.get_serializer(data=data)
            recepcion_serializer.is_valid(raise_exception=True)
            recepcion = recepcion_serializer.save()
            
            # Crear detalles
            from inventory.models import ReceptionDetail
            from inventory.serializers import ReceptionDetailSerializer
            
            detalles_creados = []
            errores_detalles = []
            
            # Imprimir para depuración
            print(f"Detalles recibidos: {detalles}")
            
            for i, detalle in enumerate(detalles):
                try:
                    # Manejar producto por uid
                    producto_uid = detalle.get('producto')
                    print(f"Producto UID: {producto_uid}, tipo: {type(producto_uid)}")
                    
                    if producto_uid and not str(producto_uid).isdigit():
                        from inventory.models import Product
                        try:
                            producto = Product.objects.get(uid=producto_uid)
                            detalle['producto'] = producto.id
                            print(f"Producto encontrado con ID: {producto.id}")
                        except Product.DoesNotExist:
                            error_msg = f"Producto con UID {producto_uid} no encontrado"
                            print(error_msg)
                            errores_detalles.append({"detalle": i, "error": error_msg})
                            continue
                    
                    detalle['recepcion'] = recepcion.id
                    detalle['business'] = perfil.business.id
                    
                    # Imprimir para depuración
                    print(f"Detalle a validar: {detalle}")
                    
                    detalle_serializer = ReceptionDetailSerializer(data=detalle)
                    if detalle_serializer.is_valid():
                        detalle_obj = detalle_serializer.save()
                        detalles_creados.append(detalle_serializer.data)
                    else:
                        print(f"Errores de validación: {detalle_serializer.errors}")
                        errores_detalles.append({"detalle": i, "error": detalle_serializer.errors})
                except Exception as e:
                    print(f"Error al procesar detalle {i}: {str(e)}")
                    errores_detalles.append({"detalle": i, "error": str(e)})
            
            # Si hay errores en los detalles pero la recepción se creó, reportarlos
            if errores_detalles:
                # Incluir los errores en la respuesta pero seguir con código 201 ya que la recepción se creó
                respuesta = recepcion_serializer.data
                respuesta['detalles'] = detalles_creados
                respuesta['errores_detalles'] = errores_detalles
                return Response(respuesta, status=status.HTTP_201_CREATED)
            
            # Si todo salió bien, devolver respuesta completa
            respuesta = recepcion_serializer.data
            respuesta['detalles'] = detalles_creados
            
            return Response(respuesta, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)

    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        proveedor_uid = self.request.data.get('proveedor')
        if proveedor_uid and not str(proveedor_uid).isdigit():
            from inventory.models import Supplier
            try:
                proveedor_obj = Supplier.objects.get(uid=proveedor_uid)
            except Supplier.DoesNotExist:
                raise ValidationError({'proveedor': 'Proveedor no encontrado para el UID especificado'})
            serializer.validated_data['proveedor'] = proveedor_obj
        serializer.save(business=perfil.business)

class SupplierViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = Supplier.objects.all()
    lookup_field = 'uid'

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
        
class ReceptionDetailViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = ReceptionDetailSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = ReceptionDetail.objects.all()
    lookup_field = 'uid'
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado para el usuario'}, status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data
        if not isinstance(data, list):
            return Response({'detail': 'Se espera una lista de detalles.'}, status=status.HTTP_400_BAD_REQUEST)
        
        detalles_creados = []
        errores = []
        
        for i, detalle in enumerate(data):
            # Validar campos obligatorios antes de procesar
            if 'producto' not in detalle:
                errores.append({
                    'indice': i,
                    'detalle': detalle,
                    'error': "El campo 'producto' es obligatorio. Debe proporcionar el UUID del producto."
                })
                continue
            
            # Eliminar el campo business si está presente
            if 'business' in detalle:
                del detalle['business']
            
            serializer = self.get_serializer(data=detalle)
            try:
                if serializer.is_valid(raise_exception=False):
                    detalle_obj = serializer.save()
                    detalles_creados.append(serializer.data)
                else:
                    errores.append({
                        'indice': i,
                        'detalle': detalle,
                        'error': serializer.errors
                    })
            except Exception as e:
                errores.append({
                    'indice': i,
                    'detalle': detalle,
                    'error': str(e)
                })
        
        respuesta = {
            'detalles_creados': detalles_creados,
            'total_creados': len(detalles_creados),
            'errores': errores
        }
        
        if len(errores) > 0 and len(detalles_creados) == 0:
            return Response(respuesta, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(respuesta, status=status.HTTP_201_CREATED)
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
        
    def perform_update(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
