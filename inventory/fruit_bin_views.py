from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import (
    DjangoFilterBackend,
    FilterSet,
    NumberFilter,
    ChoiceFilter,
    CharFilter,
    MultipleChoiceFilter,
)
from .models import FruitBin
from .fruit_bin_serializers import FruitBinListSerializer, FruitBinDetailSerializer, FruitBinBulkCreateSerializer
from core.permissions import IsSameBusiness
from accounts.models import CustomUser, Perfil


class FruitBinFilter(FilterSet):
    """Filtros personalizados para FruitBin"""
    peso_neto_min = NumberFilter(method='filter_peso_neto_min', label='Peso neto mínimo')
    peso_neto_max = NumberFilter(method='filter_peso_neto_max', label='Peso neto máximo')
    estado = CharFilter(method='filter_estado', label='Estados')
    producto = CharFilter(method='filter_producto', label='Producto (ID o nombre)')
    calidad = CharFilter(method='filter_calidad', label='Calidad/calibraje (5TA,4TA,3RA,2DA,1RA,EXTRA,SUPER_EXTRA)')
    
    def filter_peso_neto_min(self, queryset, name, value):
        """Filtra bins con peso neto mayor o igual al valor especificado"""
        if value is not None:
            filtered_bins = []
            for bin in queryset:
                if bin.peso_neto >= value:
                    filtered_bins.append(bin.pk)
            return queryset.filter(pk__in=filtered_bins)
        return queryset

    def filter_calidad(self, queryset, name, value):
        """Permite filtrar por múltiples calidades/calibrajes.
        Acepta:
        - Repetido: ?calidad=3RA&calidad=EXTRA
        - Comas: ?calidad=3RA,EXTRA
        - Arreglo: ?calidad[]=3RA&calidad[]=EXTRA
        """
        request = getattr(self, 'request', None)
        valores = []
        if request:
            valores = request.GET.getlist('calidad') or request.GET.getlist('calidad[]')
        if not valores and value:
            valores = [v.strip() for v in str(value).split(',') if v.strip()]
        if not valores:
            return queryset
        return queryset.filter(calidad__in=valores)
    
    def filter_peso_neto_max(self, queryset, name, value):
        """Filtra bins con peso neto menor o igual al valor especificado"""
        if value is not None:
            filtered_bins = []
            for bin in queryset:
                if bin.peso_neto <= value:
                    filtered_bins.append(bin.pk)
            return queryset.filter(pk__in=filtered_bins)
        return queryset

    def filter_estado(self, queryset, name, value):
        """Permite filtrar por múltiples estados.
        Acepta formatos:
        - Repetido: ?estado=DISPONIBLE&estado=EN_PROCESO
        - Comas: ?estado=DISPONIBLE,EN_PROCESO
        - Arreglo (algunos clientes): ?estado[]=DISPONIBLE&estado[]=EN_PROCESO
        """
        # Recolectar múltiples valores del querystring
        request = getattr(self, 'request', None)
        estados = []
        if request:
            estados = request.GET.getlist('estado') or request.GET.getlist('estado[]')
        # Si vino como cadena separada por comas
        if not estados and value:
            estados = [v.strip() for v in str(value).split(',') if v.strip()]
        if not estados:
            return queryset
        return queryset.filter(estado__in=estados)
    
    def filter_producto(self, queryset, name, value):
        """Filtra bins por producto, aceptando tanto ID como nombre"""
        from .models import Product
        import json
        
        if value is None:
            return queryset
        
        # Verificar si el valor es un JSON y extraer el valor real
        if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
            try:
                # Intentar parsear como JSON
                json_value = json.loads(value)
                if isinstance(json_value, list) and len(json_value) > 0:
                    # Tomar el primer valor de la lista
                    value = json_value[0]
                    # Si hay un segundo elemento que es un diccionario con una clave '0'
                    if len(json_value) > 1 and isinstance(json_value[1], dict) and '0' in json_value[1]:
                        value = json_value[1]['0']
            except json.JSONDecodeError:
                pass
        
        # Caso especial: "Todos los productos" o similar
        if isinstance(value, str) and value.lower() in ['todos los productos', 'todos', 'all', 'all products']:
            return queryset
            
        # Intentar convertir a entero para buscar por ID
        try:
            producto_id = int(value)
            return queryset.filter(producto_id=producto_id)
        except (ValueError, TypeError):
            # Si no es un ID válido, buscar por nombre
            productos = Product.objects.filter(nombre__icontains=value)
            if productos.exists():
                return queryset.filter(producto__in=productos)
            return queryset.none()
    
    class Meta:
        model = FruitBin
        fields = ['estado', 'producto', 'variedad', 'proveedor', 'calidad', 'peso_neto_min', 'peso_neto_max']


class FruitBinViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar bins de fruta.
    Permite listar, crear, actualizar y eliminar bins.
    
    Filtros disponibles:
    - estado: Filtra por el estado del bin (DISPONIBLE, EN_PROCESO, TRANSFORMADO, DESCARTADO)
    - producto: Filtra por el producto asociado al bin. Acepta tanto ID como nombre del producto
      Ejemplos: ?producto=1 o ?producto=Manzana
    - variedad: Filtra por la variedad del bin
    - proveedor: Filtra por el proveedor del bin
    - calidad: Filtra por la calidad del bin (1-5, donde 5 es Excelente)
      Ejemplo: ?calidad=4
    - peso_neto_min: Filtra bins con peso neto mayor o igual al valor especificado
      Ejemplo: ?peso_neto_min=100
    - peso_neto_max: Filtra bins con peso neto menor o igual al valor especificado
      Ejemplo: ?peso_neto_max=500
    
    También soporta búsqueda por texto en los campos: 'codigo', 'producto__nombre', 'variedad', 'proveedor__nombre'
    Ejemplo: ?search=Hass
    
    Y ordenamiento por: 'fecha_recepcion', 'codigo', 'peso_bruto'
    Ejemplo: ?ordering=-fecha_recepcion (descendente) o ?ordering=codigo (ascendente)
    """
    permission_classes = [IsAuthenticated, IsSameBusiness]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = FruitBinFilter
    search_fields = ['codigo', 'producto__nombre', 'variedad', 'proveedor__nombre']
    ordering_fields = ['fecha_recepcion', 'codigo', 'peso_bruto']
    ordering = ['-fecha_recepcion']
    lookup_field = 'uid'
    
    def get_queryset(self):
        """Filtra los bins por el negocio del usuario actual"""
        user = self.request.user
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
        
        if business:
            return FruitBin.objects.filter(business=business)
        return FruitBin.objects.none()
    
    def get_serializer_class(self):
        """Usa el serializador detallado para retrieve y el de lista para el resto"""
        if self.action == 'retrieve':
            return FruitBinDetailSerializer
        return FruitBinListSerializer

    @action(detail=True, methods=['patch'], url_path='ubicacion')
    def actualizar_ubicacion(self, request, uid=None):
        """Actualiza la ubicacion de un bin específico.
        Endpoint: PATCH /api/v1/fruit-bins/{uid}/ubicacion/
        Body: { "ubicacion": "BODEGA|PACKING|OTRO" }
        """
        bin_obj = self.get_object()
        nueva_ubicacion = request.data.get('ubicacion')
        if not nueva_ubicacion:
            raise ValidationError({'ubicacion': 'Campo requerido'})
        # Validar contra choices
        valid_values = [c[0] for c in FruitBin.UBICACION_CHOICES]
        if nueva_ubicacion not in valid_values:
            raise ValidationError({'ubicacion': f"Valor inválido. Opciones: {', '.join(valid_values)}"})
        bin_obj.ubicacion = nueva_ubicacion
        bin_obj.save(update_fields=['ubicacion', 'updated_at'])
        return Response(FruitBinDetailSerializer(bin_obj, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='ubicacion-bulk')
    def actualizar_ubicacion_bulk(self, request):
        """Actualiza la ubicacion de múltiples bins del negocio actual.
        Endpoint: POST /api/v1/fruit-bins/ubicacion-bulk/
        Body: { "bins": ["uid1","uid2",...], "ubicacion": "BODEGA|PACKING|OTRO" }
        """
        uids = request.data.get('bins') or []
        nueva_ubicacion = request.data.get('ubicacion')
        if not uids or not isinstance(uids, list):
            raise ValidationError({'bins': 'Debes enviar una lista de UIDs'})
        if not nueva_ubicacion:
            raise ValidationError({'ubicacion': 'Campo requerido'})
        valid_values = [c[0] for c in FruitBin.UBICACION_CHOICES]
        if nueva_ubicacion not in valid_values:
            raise ValidationError({'ubicacion': f"Valor inválido. Opciones: {', '.join(valid_values)}"})

        # Restringir por business del usuario
        queryset = self.get_queryset().filter(uid__in=uids)
        actualizados = []
        for b in queryset:
            b.ubicacion = nueva_ubicacion
            b.save(update_fields=['ubicacion', 'updated_at'])
            actualizados.append(b)

        data = FruitBinListSerializer(actualizados, many=True, context={'request': request}).data
        return Response({
            'cantidad_actualizada': len(actualizados),
            'ubicacion': nueva_ubicacion,
            'bins': data,
        })



class FruitBinBulkCreateView(APIView):
    """Vista para crear múltiples bins de fruta con los mismos datos"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Endpoint para crear múltiples bins de fruta con los mismos datos"""
        serializer = FruitBinBulkCreateSerializer(data=request.data)
        
        if serializer.is_valid():
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
                    {'detail': 'Usuario no tiene un negocio asociado'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Crear los bins
            bins = serializer.save(business=business)
            
            # Devolver la respuesta con los bins creados
            response_data = {
                'cantidad_creada': len(bins),
                'mensaje': f'Se han creado {len(bins)} bins correctamente',
                'bins': FruitBinListSerializer(bins, many=True).data
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
