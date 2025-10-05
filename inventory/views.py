from rest_framework import viewsets, status
from django.db.models import Q
from django.utils import timezone
from .models import BoxType, FruitLot, StockReservation, Product, GoodsReception, Supplier, ReceptionDetail, SupplierPayment, ConcessionSettlement, ConcessionSettlementDetail
from .serializers import BoxTypeSerializer, FruitLotSerializer, FruitLotListSerializer, StockReservationSerializer, ProductSerializer, GoodsReceptionSerializer, GoodsReceptionListSerializer, ReceptionDetailSerializer, SupplierPaymentSerializer, ConcessionSettlementSerializer, ConcessionSettlementDetailSerializer, PalletHistorySerializerList, PalletHistoryDetailSerializer
from .serializers_supplier import SupplierSerializerList, SupplierSerializer
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsSameBusiness, IsProveedorReadOnly
from accounts.models import CustomUser
from sales.models import SalePendingItem
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from django.db.models import Subquery, OuterRef, Sum, F, IntegerField
from django.db.models.functions import Coalesce
import json

class RolePermissionMixin:
    def get_permissions(self):
        user = self.request.user
        perms = super().get_permissions()
        # Si es Proveedor, forzar solo lectura
        try:
            if user and user.is_authenticated and user.groups.filter(name='Proveedor').exists():
                perms.append(IsProveedorReadOnly())
        except Exception:
            pass
        return perms

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        
        if perfil is None:
            return qs.none()
            
        # Proveedor: solo datos propios del proveedor asociado, solo lectura (enforced in permission)
        if user.groups.filter(name='Proveedor').exists():
            proveedor = getattr(perfil, 'proveedor', None)
            if not proveedor:
                return qs.none()
            model = getattr(qs, 'model', None)
            try:
                if model.__name__ == 'Supplier':
                    return qs.filter(pk=getattr(proveedor, 'pk', None))
                if model.__name__ == 'GoodsReception':
                    return qs.filter(proveedor=proveedor)
                if model.__name__ == 'ReceptionDetail':
                    return qs.filter(recepcion__proveedor=proveedor)
                if model.__name__ == 'FruitLot':
                    return qs.filter(Q(proveedor=proveedor) | Q(propietario_original=proveedor))
                if model.__name__ == 'SupplierPayment':
                    return qs.filter(recepcion__proveedor=proveedor)
                if model.__name__ == 'ConcessionSettlement':
                    return qs.filter(proveedor=proveedor)
                if model.__name__ == 'ConcessionSettlementDetail':
                    return qs.filter(liquidacion__proveedor=proveedor)
            except Exception:
                return qs.none()
            # Si no está mapeado, no exponer datos
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
    
    def get_serializer_class(self):
        """Usa un serializer diferente para la lista y el detalle."""
        if self.action == 'list':
            return FruitLotListSerializer
        elif self.action == 'sold_pallets':
            return PalletHistorySerializerList
        elif self.action == 'sold_pallet_detail':
            return PalletHistoryDetailSerializer
        return FruitLotSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Subquery para calcular el total de cajas reservadas para cada lote
        reservas_cajas_subquery = StockReservation.objects.filter(
            lote=OuterRef('pk'), 
            estado='en_proceso'
        ).values('lote').annotate(
            total_reservado=Sum('cajas_reservadas')
        ).values('total_reservado')

        # Subquery para calcular el total de unidades reservadas para productos no-palta
        reservas_unidades_subquery = StockReservation.objects.filter(
            lote=OuterRef('pk'), 
            estado='en_proceso'
        ).values('lote').annotate(
            total_unidades=Sum('unidades_reservadas')
        ).values('total_unidades')

        # Anotar el queryset con el stock disponible
        qs = qs.annotate(
            cajas_reservadas=Coalesce(
                Subquery(reservas_cajas_subquery, output_field=IntegerField()), 
                0
            ),
            total_unidades_reservadas=Coalesce(
                Subquery(reservas_unidades_subquery, output_field=IntegerField()),
                0
            )
        ).annotate(
            stock_disponible_cajas=F('cantidad_cajas') - F('cajas_reservadas')
        )

        # Verificar si hay un filtro específico por estado_lote
        estado_lote = self.request.query_params.get('estado_lote', None)
        tipo_producto = self.request.query_params.get('tipo_producto', None)
        
        # Filtrar por estado y stock disponible directamente en el queryset
        if estado_lote is not None:
            qs = qs.filter(estado_lote=estado_lote)
        else:
            # Mostrar todos los lotes que tengan cajas disponibles, independientemente del tipo de producto
            # Esto asegura que se muestren tanto paltas como otros productos
            qs = qs.filter(cantidad_cajas__gt=0)
        
        # Filtrar por tipo de producto si se especifica
        if tipo_producto is not None:
            qs = qs.filter(producto__tipo_producto=tipo_producto)
            
        return qs.order_by('-created_at')

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
    
    @action(detail=True, methods=['post'])
    def update_maturation(self, request, uid=None):
        """Actualiza el estado de maduración de un lote de fruta"""
        try:
            lote = self.get_object()
            nuevo_estado = request.data.get('estado_maduracion')
            if not nuevo_estado:
                return Response({'error': 'Se requiere el campo estado_maduracion'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Validar que el estado sea uno de los permitidos
            estados_validos = ['verde', 'pre-maduro', 'maduro', 'sobremaduro']
            if nuevo_estado not in estados_validos:
                return Response({'error': f'Estado inválido. Debe ser uno de: {estados_validos}'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Actualizar el estado
            lote.estado_maduracion = nuevo_estado
            lote.fecha_maduracion = timezone.now().date()
            lote.save()
            
            # Registrar el cambio en el historial
            from .models import MadurationHistory
            MadurationHistory.objects.create(
                lote=lote,
                estado_maduracion=nuevo_estado
            )
            
            return Response({'status': 'success', 'message': f'Estado de maduración actualizado a {nuevo_estado}'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
    @action(detail=False, methods=['get'])
    def sold_pallets(self, request):
        """Retorna una lista de pallets vendidos o con estado agotado"""
        try:
            # Filtrar pallets vendidos o agotados basándose únicamente en cajas, no en kilos disponibles
            queryset = FruitLot.objects.filter(cantidad_cajas=0)
            
            # Aplicar filtros adicionales si se proporcionan
            producto_id = request.query_params.get('producto_id')
            if producto_id:
                queryset = queryset.filter(producto__uid=producto_id)
                
            proveedor = request.query_params.get('proveedor')
            if proveedor:
                queryset = queryset.filter(proveedor__icontains=proveedor)
                
            procedencia = request.query_params.get('procedencia')
            if procedencia:
                queryset = queryset.filter(procedencia__icontains=procedencia)
                
            fecha_desde = request.query_params.get('fecha_desde')
            if fecha_desde:
                queryset = queryset.filter(fecha_ingreso__gte=fecha_desde)
                
            fecha_hasta = request.query_params.get('fecha_hasta')
            if fecha_hasta:
                queryset = queryset.filter(fecha_ingreso__lte=fecha_hasta)
            
            # Ordenar por fecha de ingreso descendente (más reciente primero)
            queryset = queryset.order_by('-fecha_ingreso')
            
            # Paginar resultados
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
    @action(detail=True, methods=['get'])
    def sold_pallet_detail(self, request, uid=None):
        """Retorna el detalle de un pallet vendido o agotado, con información específica según el tipo de fruta"""
        try:
            # Obtener el lote directamente por su UID
            try:
                lote = FruitLot.objects.get(uid=uid)
            except FruitLot.DoesNotExist:
                return Response({'error': f'No existe un pallet con el ID: {uid}'}, status=status.HTTP_404_NOT_FOUND)
            
            # Verificar que el lote no tenga cajas disponibles (basado solo en cajas, no en kilos)
            if lote.cantidad_cajas > 0:
                return Response(
                    {'error': 'Este pallet todavía tiene cajas disponibles'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = self.get_serializer(lote)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
    
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('-created_at')
    
    def get_serializer_class(self):
        """Usa el serializer simplificado para listas y el completo para detalles"""
        if self.action == 'list':
            return GoodsReceptionListSerializer
        return GoodsReceptionSerializer
    
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
            
            # Capturar configuración de comisión desde la recepción
            comision_base = data.get('comision_base')
            comision_monto = data.get('comision_monto')
            comision_porcentaje = data.get('comision_porcentaje')
            en_concesion = data.get('en_concesion', False)
            fecha_limite_concesion = data.get('fecha_limite_concesion')

            comision_por_kilo_resuelta = None

            for i, detalle in enumerate(detalles):
                try:
                    # Manejar producto por uid
                    producto_val = detalle.get('producto')
                    print(f"Producto valor: {producto_val}, tipo: {type(producto_val)}")
                    # ReceptionDetailSerializer espera slug uid para 'producto'
                    from inventory.models import Product
                    if producto_val is None:
                        errores_detalles.append({"detalle": i, "error": "Campo 'producto' es obligatorio"})
                        continue
                    if str(producto_val).isdigit():
                        # Si viene como ID numérico, convertir a UID
                        try:
                            producto_obj = Product.objects.get(id=int(producto_val))
                            detalle['producto'] = str(producto_obj.uid)
                        except Product.DoesNotExist:
                            error_msg = f"Producto con ID {producto_val} no encontrado"
                            print(error_msg)
                            errores_detalles.append({"detalle": i, "error": error_msg})
                            continue
                    else:
                        # Validar que el UID exista
                        try:
                            producto_obj = Product.objects.get(uid=producto_val)
                            detalle['producto'] = str(producto_obj.uid)
                        except Product.DoesNotExist:
                            error_msg = f"Producto con UID {producto_val} no encontrado"
                            print(error_msg)
                            errores_detalles.append({"detalle": i, "error": error_msg})
                            continue
                    
                    # ReceptionDetailSerializer espera slug uid para 'recepcion'
                    detalle['recepcion'] = str(recepcion.uid)
                    detalle['business'] = perfil.business.id
                    
                    # Imprimir para depuración
                    print(f"Detalle a validar: {detalle}")
                    
                    # Calcular comisión por kilo si corresponde (base 'kg')
                    try:
                        from decimal import Decimal as D
                        # Solo si la recepción está en concesión
                        if en_concesion and (comision_base == 'kg'):
                            # Preferir monto directo, sino calcular por porcentaje con costo del detalle
                            if comision_monto not in (None, ''):
                                detalle['comision_por_kilo'] = D(str(comision_monto))
                                comision_por_kilo_resuelta = D(str(comision_monto))
                            elif comision_porcentaje not in (None, ''):
                                costo_det = detalle.get('costo')
                                if costo_det not in (None, ''):
                                    detalle['comision_por_kilo'] = D(str(costo_det)) * D(str(comision_porcentaje)) / D('100')
                                    comision_por_kilo_resuelta = detalle['comision_por_kilo']
                    except Exception:
                        pass

                    # Propagar flags de concesión a cada detalle
                    detalle['en_concesion'] = en_concesion
                    detalle['fecha_limite_concesion'] = fecha_limite_concesion

                    # Actualizar por uid si viene, si no crear
                    detalle_uid = detalle.get('uid')
                    if detalle_uid:
                        existente = ReceptionDetail.objects.filter(uid=detalle_uid, recepcion=recepcion).first()
                        if existente:
                            detalle_serializer = ReceptionDetailSerializer(existente, data=detalle, partial=True)
                            if detalle_serializer.is_valid():
                                detalle_serializer.save()
                                detalles_creados.append(detalle_serializer.data)
                            else:
                                print(f"Errores de validación (update): {detalle_serializer.errors}")
                                errores_detalles.append({"detalle": i, "error": detalle_serializer.errors})
                            continue
                    detalle_serializer = ReceptionDetailSerializer(data=detalle)
                    if detalle_serializer.is_valid():
                        detalle_serializer.save()
                        detalles_creados.append(detalle_serializer.data)
                    else:
                        print(f"Errores de validación (create): {detalle_serializer.errors}")
                        errores_detalles.append({"detalle": i, "error": detalle_serializer.errors})
                except Exception as e:
                    print(f"Error al procesar detalle {i}: {str(e)}")
                    errores_detalles.append({"detalle": i, "error": str(e)})
            
            # Si hay errores en los detalles pero la recepción se creó, reportarlos
            if errores_detalles:
                # Re-serializar la recepción para que 'detalles' venga del GoodsReceptionSerializer (incluye comisión)
                recepcion_refrescada = GoodsReception.objects.get(pk=recepcion.pk)
                respuesta = self.get_serializer(recepcion_refrescada).data
                respuesta['errores_detalles'] = errores_detalles
                # Si resolvimos una comisión por kilo, reflejarla a nivel de recepción
                try:
                    if comision_por_kilo_resuelta is not None:
                        recepcion.comision_por_kilo = comision_por_kilo_resuelta
                        recepcion.save(update_fields=['comision_por_kilo'])
                        # Recalcular serializer para incluir campo actualizado
                        respuesta['comision_por_kilo'] = float(comision_por_kilo_resuelta)
                except Exception:
                    pass
                return Response(respuesta, status=status.HTTP_201_CREATED)
            
            # Si todo salió bien, devolver respuesta completa con 'detalles' ricos (incluye comisión)
            recepcion_refrescada = GoodsReception.objects.get(pk=recepcion.pk)
            respuesta = self.get_serializer(recepcion_refrescada).data
            # Si resolvimos una comisión por kilo, reflejarla a nivel de recepción
            try:
                if comision_por_kilo_resuelta is not None:
                    recepcion.comision_por_kilo = comision_por_kilo_resuelta
                    recepcion.save(update_fields=['comision_por_kilo'])
                    respuesta['comision_por_kilo'] = float(comision_por_kilo_resuelta)
            except Exception:
                pass
            
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
    
    def get_serializer_class(self):
        """Utiliza diferentes serializadores según la acción"""
        if self.action == 'list':
            return SupplierSerializerList
        return SupplierSerializer

    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)
        
    @action(detail=True, methods=['get'])
    def transactions(self, request, uid=None):
        """
        Obtiene todas las recepciones de mercancía (GoodsReception) vinculadas a este proveedor
        """
        try:
            # Obtener el proveedor
            supplier = self.get_object()
            
            # Obtener todas las recepciones asociadas a este proveedor
            receptions = GoodsReception.objects.filter(proveedor=supplier).order_by('-fecha_recepcion')
            
            # Serializar los resultados
            serializer = GoodsReceptionSerializer(receptions, many=True)
            
            return Response({
                'count': receptions.count(),
                'results': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Error al obtener transacciones: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ReceptionDetailViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = ReceptionDetailSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = ReceptionDetail.objects.all()
    lookup_field = 'uid'
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Actualiza detalles existentes o crea nuevos para una recepción"""
        import logging
        logger = logging.getLogger(__name__)
        user = request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            return Response({'detail': 'Perfil no encontrado para el usuario'}, status=status.HTTP_400_BAD_REQUEST)
    
        data = request.data
        logger.info(f"Datos recibidos: {data}")
        if not isinstance(data, dict) or 'recepcion_uid' not in data or 'detalles' not in data:
            return Response({
                'detail': 'Formato incorrecto. Se espera un objeto con recepcion_uid y detalles.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        recepcion_uid = data['recepcion_uid']
        detalles_data = data['detalles']
        
        try:
            # Verificar que la recepción existe y pertenece al negocio del usuario
            recepcion = GoodsReception.objects.get(uid=recepcion_uid, business=perfil.business)
        except GoodsReception.DoesNotExist:
            return Response({'detail': 'Recepción no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        
        detalles_actualizados = []
        detalles_creados = []
        errores = []
        
        for i, detalle_data in enumerate(detalles_data):
            # Asignar la recepción a cada detalle
            detalle_data['recepcion'] = recepcion.uid
            # Normalizar 'producto' a UID, ya que el serializer espera slug_field='uid'
            try:
                from inventory.models import Product
                producto_val = detalle_data.get('producto')
                if producto_val is None:
                    errores.append({
                        'indice': i,
                        'detalle': detalle_data,
                        'error': "El campo 'producto' es obligatorio."
                    })
                    continue
                if str(producto_val).isdigit():
                    try:
                        producto_obj = Product.objects.get(id=int(producto_val))
                        detalle_data['producto'] = str(producto_obj.uid)
                    except Product.DoesNotExist:
                        errores.append({
                            'indice': i,
                            'detalle': detalle_data,
                            'error': f"Producto con ID {producto_val} no encontrado"
                        })
                        continue
                else:
                    try:
                        producto_obj = Product.objects.get(uid=producto_val)
                        detalle_data['producto'] = str(producto_obj.uid)
                    except Product.DoesNotExist:
                        errores.append({
                            'indice': i,
                            'detalle': detalle_data,
                            'error': f"Producto con UID {producto_val} no encontrado"
                        })
                        continue
            except Exception as e:
                errores.append({
                    'indice': i,
                    'detalle': detalle_data,
                    'error': f"Error al normalizar producto: {str(e)}"
                })
                continue
            
            # Verificar si es una actualización o creación
            es_actualizacion = 'uid' in detalle_data and detalle_data['uid']
            
            # Log de datos del detalle
            logger.info(f"Procesando detalle {i}: {detalle_data}")
            if 'precio_sugerido_min' in detalle_data:
                logger.info(f"Precio sugerido min: {detalle_data['precio_sugerido_min']} (tipo: {type(detalle_data['precio_sugerido_min'])})")
            
            try:
                if es_actualizacion:
                    # Actualizar detalle existente
                    try:
                        # Verificar que el detalle pertenece a la recepción correcta
                        detalle_obj = ReceptionDetail.objects.get(uid=detalle_data['uid'], recepcion__business=perfil.business)
                        serializer = self.get_serializer(detalle_obj, data=detalle_data, partial=True)
                        if serializer.is_valid(raise_exception=False):
                            logger.info(f"Serializer válido para actualización: {serializer.validated_data}")
                            serializer.save()  # No pasar business aquí
                            detalles_actualizados.append(serializer.data)
                        else:
                            logger.error(f"Error en serializer para actualización: {serializer.errors}")
                            errores.append({
                                'indice': i,
                                'detalle': detalle_data,
                                'error': serializer.errors
                            })
                    except ReceptionDetail.DoesNotExist:
                        errores.append({
                            'indice': i,
                            'detalle': detalle_data,
                            'error': 'Detalle no encontrado'
                        })
                else:
                    # Crear nuevo detalle o actualizar si ya existe por uid
                    # Validar campos obligatorios
                    if 'producto' not in detalle_data:
                        errores.append({
                            'indice': i,
                            'detalle': detalle_data,
                            'error': "El campo 'producto' es obligatorio."
                        })
                        continue
                    # Upsert por uid si se entrega
                    detalle_uid = detalle_data.get('uid')
                    existente = ReceptionDetail.objects.filter(uid=detalle_uid, recepcion=recepcion).first() if detalle_uid else None
                    if existente:
                        serializer = self.get_serializer(existente, data=detalle_data, partial=True)
                        if serializer.is_valid(raise_exception=False):
                            logger.info(f"Serializer válido para actualización por upsert: {serializer.validated_data}")
                            serializer.save()
                            detalles_actualizados.append(serializer.data)
                        else:
                            logger.error(f"Error en serializer para actualización por upsert: {serializer.errors}")
                            errores.append({
                                'indice': i,
                                'detalle': detalle_data,
                                'error': serializer.errors
                            })
                    else:
                        serializer = self.get_serializer(data=detalle_data)
                        if serializer.is_valid(raise_exception=False):
                            logger.info(f"Serializer válido para creación: {serializer.validated_data}")
                            serializer.save()
                            detalles_creados.append(serializer.data)
                        else:
                            logger.error(f"Error en serializer para creación: {serializer.errors}")
                            errores.append({
                                'indice': i,
                                'detalle': detalle_data,
                                'error': serializer.errors
                            })
            except Exception as e:
                errores.append({
                    'indice': i,
                    'detalle': detalle_data,
                    'error': str(e)
                })
        
        respuesta = {
            'detalles_actualizados': detalles_actualizados,
            'detalles_creados': detalles_creados,
            'total_actualizados': len(detalles_actualizados),
            'total_creados': len(detalles_creados),
            'errores': errores
        }
        
        if len(errores) > 0 and len(detalles_actualizados) == 0 and len(detalles_creados) == 0:
            return Response(respuesta, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(respuesta, status=status.HTTP_200_OK)
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)

class SupplierPaymentViewSet(RolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = SupplierPaymentSerializer
    permission_classes = [IsAuthenticated, IsSameBusiness]
    queryset = SupplierPayment.objects.all()
    lookup_field = 'uid'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtrar por recepci�n si se proporciona el par�metro
        recepcion_uid = self.request.query_params.get('recepcion', None)
        if recepcion_uid:
            qs = qs.filter(recepcion__uid=recepcion_uid)
        
        # Filtrar por proveedor si se proporciona el par�metro
        proveedor_uid = self.request.query_params.get('proveedor', None)
        if proveedor_uid:
            qs = qs.filter(recepcion__proveedor__uid=proveedor_uid)
            
        return qs
    
    def perform_create(self, serializer):
        user = self.request.user
        perfil = getattr(user, 'perfil', None)
        if perfil is None:
            raise ValidationError({'detail': 'Perfil no encontrado para el usuario'})
        serializer.save(business=perfil.business)

